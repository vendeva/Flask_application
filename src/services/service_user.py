import sqlite3
from flask import (
    request,
)
from services.service_ads import AdsService
from werkzeug.security import generate_password_hash
from exceptions import ServiceError


class UserForbiddenError(ServiceError):
    pass

class UserBadRequestError(ServiceError):
    pass

class UserDoesNotExistError(ServiceError):
    pass

class UserIntegrityError(ServiceError):
    pass

class UserService:
    def __init__(self, connection):
        self.connection = connection

    def get_user(self, user_id):
        cur = self.connection.execute('''
            SELECT account.id, email, first_name, last_name                 
            FROM  account  
            WHERE account.id = ?''',
            (user_id,),
        )
        user = cur.fetchone()
        if user is None:
            raise UserDoesNotExistError
        cur = self.connection.execute('''
            SELECT phone, seller.zip_code, city_id, street, home 
            FROM  seller                
                JOIN zipcode ON seller.zip_code = zipcode.zip_code 
            WHERE account_id = ?''',
            (user_id,),
        )
        seller = cur.fetchone()
        if seller is None:
            return {**dict(user), "seller": False}
        return {**dict(user), "seller": True, **dict(seller)}


    def post_user(self):
        request_json = request.json
        if self.is_empty_field(request_json):
            raise UserBadRequestError

        account = ['first_name', 'last_name', 'email']
        account_dict = {key: value for key, value in request_json.items()
                        if key in account}
        password = request_json.get('password')
        is_seller = request_json.get('is_seller')
        password_hash = generate_password_hash(password)

        try:
            account_params = ', '.join([*account_dict.keys(), "password"])
            account_values = [*account_dict.values(), password_hash]
            account_query = f'''
                INSERT INTO account ({account_params})
                VAlUES (?, ?, ?, ?) 
            '''
            cur = self.connection.execute(account_query, (*account_values,))
            account_id = cur.lastrowid


            if is_seller:
                self.make_seller_zipcode(account_id, request_json)

            self.connection.commit()

        except sqlite3.IntegrityError:
            raise UserIntegrityError

        rows = {key: value for key, value in request_json.items()
                if "password" not in key}

        return {"id": account_id, **rows}


    def patch_user(self, user_id):
        cur = self.connection.execute(
            'SELECT id '
            'FROM  account '
            'WHERE id = ? ',
            (user_id,),
        )
        user = cur.fetchone()
        if user is None:
            raise UserDoesNotExistError

        request_json = request.json
        if self.is_empty_field(request_json):
            raise UserBadRequestError


        account = ['first_name', 'last_name']
        account_dict = {key: value for key, value in request_json.items()
                        if key in account}

        try:
            account_params = ','.join(f'{key} = ?' for key in account_dict.keys())
            if account_params:
                account_query = f'UPDATE account SET {account_params} WHERE id = ?'
                self.connection.execute(account_query, (*account_dict.values(), user_id))

            is_seller = request_json.get('is_seller')
            if is_seller:
                seller = ['zip_code', 'street', 'home', 'phone']
                seller_dict = {key: value for key, value in request_json.items()
                               if key in seller}

                cur = self.connection.execute(
                    'SELECT city_id '
                    'FROM  zipcode '
                        'JOIN seller ON zipcode.zip_code = seller.zip_code '
                    'WHERE account_id = ? ',
                    (user_id,),
                )
                result_zipcode = cur.fetchone()
                if result_zipcode is None:
                    self.make_seller_zipcode(user_id, request_json)
                else:
                    city_id_old_value = result_zipcode["city_id"]
                    seller_params = ','.join(f'{key} = ?' for key in seller_dict.keys())
                    seller_query = f'UPDATE seller SET {seller_params} WHERE account_id = ? '
                    self.connection.execute(seller_query, (*seller_dict.values(), user_id))

                    zip_code = request_json.get('zip_code')
                    city_id = request_json.get('city_id')
                    if city_id and zip_code is None:
                        raise UserBadRequestError
                    if zip_code and city_id is None:
                        city_id = city_id_old_value
                    cur = self.connection.execute(
                        'SELECT city_id '
                        'FROM  zipcode '
                        'WHERE zip_code = ? ',
                        (zip_code,),
                    )
                    zip_code_result = cur.fetchone()
                    if zip_code_result and zip_code_result["city_id"] != city_id:
                        raise sqlite3.IntegrityError
                    zipcode_query = '''
                        INSERT OR IGNORE INTO zipcode (zip_code, city_id)
                        VAlUES (?, ?) 
                    '''
                    self.connection.execute(zipcode_query, (zip_code, city_id))

            else:
                cur = self.connection.execute(
                    'SELECT ad.id as ad_id, ad.car_id '
                    'FROM  ad '
                        'JOIN seller ON seller.id = ad.seller_id '
                    'WHERE seller.account_id = ? ',
                    (user_id,),
                )
                result_ad = cur.fetchall()

                for row in result_ad:
                    ad_id, car_id = dict(row).values()

                    self.connection.execute(
                        'DELETE FROM seller '
                        'WHERE account_id = ? ',
                        (user_id,),
                    )

                    service = AdsService(self.connection)
                    service.delete_ad(ad_id, car_id)


            cur = self.connection.execute(
                'SELECT email '
                'FROM account '
                'WHERE id = ? ',
                (user_id,),
            )
            email = cur.fetchone()

            self.connection.commit()

        except sqlite3.IntegrityError:
            raise UserIntegrityError

        return {"id": user_id, "email": email["email"], **request.json}


    def make_seller_zipcode(self, user_id, request):
        seller = ['phone', 'zip_code', 'street', 'home']
        zipcode = ['zip_code', 'city_id']
        seller_dict = {key: value for key, value in request.items()
                       if key in seller}
        zipcode_dict = {key: value for key, value in request.items()
                        if key in zipcode}


        if seller_dict and len(seller_dict) == 4:
            seller_params = ', '.join([*seller_dict.keys(), "account_id"])
            seller_query = f'''
                INSERT INTO seller ({seller_params})
                VAlUES (?, ?, ?, ?, ?)
            '''
            self.connection.execute(seller_query, (*seller_dict.values(), user_id))
        else:
            raise sqlite3.IntegrityError


        zip_code = request.get('zip_code')
        city_id = request.get('city_id')
        cur = self.connection.execute(
            'SELECT * '
            'FROM  zipcode '
            'WHERE zip_code = ? ',
            (zip_code,),
        )
        zip_code_result = cur.fetchone()
        if zip_code_result and city_id is None:
            zipcode_dict["city_id"] = zip_code_result["city_id"]
        if zip_code_result and dict(zip_code_result) != zipcode_dict:
            raise sqlite3.IntegrityError
        if zipcode_dict and len(zipcode_dict) == 2:
            zipcode_params = ', '.join(zipcode_dict.keys())
            zipcode_query = f'''
                INSERT OR IGNORE INTO zipcode ({zipcode_params})
                VAlUES (?, ?) 
            '''
            self.connection.execute(zipcode_query, (*zipcode_dict.values(),))
        else:
            raise sqlite3.IntegrityError

    def is_empty_field(self, request):
        for value in request.values():
            if not value and not isinstance(value, bool):
                return True
