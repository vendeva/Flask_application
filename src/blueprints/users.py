import sqlite3
from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)
from flask.views import MethodView
from werkzeug.security import generate_password_hash

from database import db


bp = Blueprint('users', __name__)


class UsersView(MethodView):
    def post(self):
        request_json = request.json
        for value in request_json.values():
            if not value and not isinstance(value, bool):
                return '', 400

        account = ['first_name', 'last_name', 'email']
        seller = ['phone', 'zip_code', 'street', 'home']
        zipcode = ['zip_code', 'city_id']

        request_json = request.json
        account_dict = {key: value for key, value in request_json.items()
                        if key in account}
        password = request_json.get('password')
        password_hash = generate_password_hash(password)


        con = db.connection
        try:
            account_params = ', '.join([*account_dict.keys(), "password"])
            account_values = [*account_dict.values(), password_hash]
            account_query = f'''
                INSERT INTO account ({account_params})
                VAlUES (?, ?, ?, ?) 
                '''
            cur = con.execute(account_query, (*account_values,))

            account_id = cur.lastrowid
            is_seller = request_json.get('is_seller')

            if is_seller:
                seller_dict = {key: value for key, value in request_json.items()
                               if key in seller}
                zipcode_dict = {key: value for key, value in request_json.items()
                                if key in zipcode}


                seller_params = ', '.join([*seller_dict.keys(), "account_id"])
                seller_values = [*seller_dict.values(), account_id]
                seller_query = f'''
                    INSERT INTO seller ({seller_params})
                    VAlUES (?, ?, ?, ?, ?) 
                    '''
                con.execute(seller_query, (*seller_values,))

                zip_code = request_json.get('zip_code')
                cur = con.execute(
                    'SELECT * '
                    'FROM  zipcode '
                    'WHERE zip_code = ? ',
                    (zip_code,),
                )
                zip_code_result = cur.fetchone()
                if zip_code_result and dict(zip_code_result) != zipcode_dict:
                    raise sqlite3.IntegrityError


                zipcode_params = ', '.join(zipcode_dict.keys())
                zipcode_query = f'''
                    INSERT OR IGNORE INTO zipcode ({zipcode_params})
                    VAlUES (?, ?) 
                    '''
                con.execute(zipcode_query, (*zipcode_dict.values(),))

                con.commit()
        except sqlite3.IntegrityError:
            return '', 409

        rows = {key: value for key, value in request_json.items()
                if "password" not in key}

        return jsonify({"id": account_id, **rows}), 201


class UserView(MethodView):
    def get(self, user_id):
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403


        con = db.connection
        cur = con.execute(
            'SELECT '
                'account.id, email, first_name, last_name, '
                'phone, seller.zip_code, city_id, street, home '
            'FROM  account '
                'JOIN seller ON account.id = seller.account_id '
                'JOIN zipcode ON seller.zip_code = zipcode.zip_code ' 
            'WHERE account.id = ?',
            (user_id,),
        )
        user = cur.fetchone()
        if user is None:
            return '', 404
        return jsonify(dict(user))

    def patch(self, user_id):
        session_id = session.get('user_id')
        if session_id is None or session_id != user_id:
            return '', 403

        con = db.connection
        cur = con.execute(
            'SELECT id '
            'FROM  account '
            'WHERE id = ? ',
            (user_id,),
        )
        user = cur.fetchone()
        if user is None:
            return '', 404

        request_json = request.json
        for value in request_json.values():
            if not value and not isinstance(value, bool):
                return '', 400

        account = ['first_name', 'last_name']
        seller = ['zip_code', 'street', 'home', 'phone']


        account_dict = {key: value for key, value in request_json.items()
                        if key in account}

        try:
            account_params = ','.join(f'{key} = ?' for key in account_dict.keys())
            account_query = f'UPDATE account SET {account_params} WHERE id = ?'
            con.execute(account_query, (*account_dict.values(), user_id))

            is_seller = request_json.get('is_seller')
            if is_seller:
                seller_dict = {key: value for key, value in request_json.items()
                               if key in seller}

                cur = con.execute(
                    'SELECT city_id '
                    'FROM  zipcode '
                        'JOIN seller ON zipcode.zip_code = seller.zip_code '
                    'WHERE account_id = ? ',
                    (user_id,),
                )
                result_zipcode = cur.fetchone()

                if result_zipcode is None:
                    return '', 400

                city_id_old_value = result_zipcode["city_id"]

                seller_params = ','.join(f'{key} = ?' for key in seller_dict.keys())
                seller_query = f'UPDATE seller SET {seller_params} WHERE account_id = ? '
                con.execute(seller_query, (*seller_dict.values(), user_id))


                zip_code = request_json.get('zip_code')
                city_id = request_json.get('city_id')
                if city_id and zip_code is None:
                    return '', 400
                if zip_code and not city_id:
                    city_id = city_id_old_value

                cur = con.execute(
                    'SELECT city_id '
                    'FROM  zipcode '
                    'WHERE zip_code = ? ',
                    (zip_code,),
                )
                zip_code_result = cur.fetchone()
                if zip_code_result and zip_code_result["city_id"] != city_id:
                    raise sqlite3.IntegrityError

                zipcode_query = f'''
                    INSERT OR IGNORE INTO zipcode (zip_code, city_id)
                    VAlUES (?, ?) 
                    '''
                con.execute(zipcode_query, (zip_code, city_id))

            else:
                cur = con.execute(
                    'SELECT ad.id as ad_id, ad.car_id '
                    'FROM  ad '
                        'JOIN seller ON seller.id = ad.seller_id '  
                    'WHERE seller.account_id = ? ',
                    (user_id,),
                )
                result_ad = cur.fetchall()

                for row in result_ad:
                    ad_id, car_id = dict(row).values()

                    con.execute(
                        'DELETE FROM seller '
                        'WHERE account_id = ? ',
                        (user_id,),
                    )


                    con.executescript(f"""
                        DELETE FROM ad
                        WHERE id = {ad_id};

                        DELETE FROM adtag
                        WHERE ad_id = {ad_id};

                        DELETE FROM car
                        WHERE id = {car_id};

                        DELETE FROM image
                        WHERE car_id = {car_id};

                        DELETE FROM carcolor
                        WHERE car_id = {car_id};
                    """)


            cur = con.execute(
                'SELECT email '
                'FROM account '
                'WHERE id = ? ',
                (user_id,),
            )
            email = cur.fetchone()
            con.commit()

        except sqlite3.IntegrityError:
            return '', 409

        return jsonify({"id": user_id, "email": email["email"], **request.json}), 200



bp.add_url_rule('', view_func=UsersView.as_view('users'))
bp.add_url_rule('/<int:user_id>', view_func=UserView.as_view('user'))
