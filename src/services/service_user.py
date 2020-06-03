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
        # Проверка пользователя на существование по переданному id
        cur = self.connection.execute('''
            SELECT account.id, email, first_name, last_name                 
            FROM  account  
            WHERE account.id = ?''',
            (user_id,),
        )
        user = cur.fetchone()
        # Если пользователь не найден -> 404
        if user is None:
            raise UserDoesNotExistError
        # Проверка продавца на существование по переданному id
        cur = self.connection.execute('''
            SELECT phone, seller.zip_code, city_id, street, home 
            FROM  seller                
                JOIN zipcode ON seller.zip_code = zipcode.zip_code 
            WHERE account_id = ?''',
            (user_id,),
        )
        seller = cur.fetchone()
        # Если продавец не найден возвращаем данные пользователя и seller:false,
        # иначе -> полученные данные
        if seller is None:
            return {**dict(user), "seller": False}
        return {**dict(user), "seller": True, **dict(seller)}


    def post_user(self):
        # Проверка заполнены ли переданные поля, иначе -> 400
        request_json = request.json
        if self.is_empty_field(request_json):
            raise UserBadRequestError

        # Структуризация исходных данных
        account = ['first_name', 'last_name', 'email']
        account_dict = {key: value for key, value in request_json.items()
                        if key in account}
        password = request_json.get('password')
        is_seller = request_json.get('is_seller')
        password_hash = generate_password_hash(password)

        try:
            # Запись в таблицу account
            account_params = ', '.join([*account_dict.keys(), "password"])
            account_values = [*account_dict.values(), password_hash]
            account_query = f'''
                INSERT INTO account ({account_params})
                VAlUES (?, ?, ?, ?) 
            '''
            cur = self.connection.execute(account_query, (*account_values,))
            account_id = cur.lastrowid

            # Запись в таблицу seller, если seller: true, вызываем метод
            # для создания продавца и записи его адресных данных в таблицу zipcode
            if is_seller:
                self.make_seller_zipcode(account_id, request_json)

            self.connection.commit()

        except sqlite3.IntegrityError:
            raise UserIntegrityError
        # Исключение пароля из вывода данных
        rows = {key: value for key, value in request_json.items()
                if "password" not in key}

        return {"id": account_id, **rows}


    def patch_user(self, user_id):
        # Проверка пользователя на существование по переданному id
        cur = self.connection.execute(
            'SELECT id '
            'FROM  account '
            'WHERE id = ? ',
            (user_id,),
        )
        user = cur.fetchone()
        # Если пользователь не найден -> 404
        if user is None:
            raise UserDoesNotExistError

        # Проверка заполнены ли переданные поля, иначе -> 400
        request_json = request.json
        if self.is_empty_field(request_json):
            raise UserBadRequestError

        # Структуризация исходных данных по пользователю
        account = ['first_name', 'last_name']
        account_dict = {key: value for key, value in request_json.items()
                        if key in account}

        try:
            # Обновление таблицы account
            account_params = ','.join(f'{key} = ?' for key in account_dict.keys())
            if account_params:
                account_query = f'UPDATE account SET {account_params} WHERE id = ?'
                self.connection.execute(account_query, (*account_dict.values(), user_id))

            # Работа с таблицей seller и zipcode, если seller true
            is_seller = request_json.get('is_seller')
            if is_seller:
                # Структуризация исходных данных по продавцу
                seller = ['zip_code', 'street', 'home', 'phone']
                seller_dict = {key: value for key, value in request_json.items()
                               if key in seller}

                # Проверка существования продавца у текущего пользователя
                cur = self.connection.execute(
                    'SELECT city_id '
                    'FROM  zipcode '
                        'JOIN seller ON zipcode.zip_code = seller.zip_code '
                    'WHERE account_id = ? ',
                    (user_id,),
                )
                result_zipcode = cur.fetchone()
                # Если продавца нет то создаем его для данного пользователя,
                # вызываем  метод для создания продавца и записи его адресных данных
                # в таблицу zipcode
                if result_zipcode is None:
                    self.make_seller_zipcode(user_id, request_json)
                # Работа с таблицей seller и zipcode, если продавец есть
                else:
                    # Получение id города продавца до обновления данных
                    city_id_old_value = result_zipcode["city_id"]
                    # Обновление таблицы seller если переданы параметры
                    seller_params = ','.join(f'{key} = ?' for key in seller_dict.keys())
                    seller_query = f'UPDATE seller SET {seller_params} WHERE account_id = ? '
                    self.connection.execute(seller_query, (*seller_dict.values(), user_id))


                    zip_code = request_json.get('zip_code')
                    city_id = request_json.get('city_id')
                    # Если переданы city_id, но нет zipcode -> 400
                    if city_id and zip_code is None:
                        raise UserBadRequestError
                    # Если передан zipcode, но нет city_id, то присваиваем значение,
                    # полученное до обновления таблицы seller
                    if zip_code and city_id is None:
                        city_id = city_id_old_value
                    # Поиск в таблице zipcode значений по переданному zipcode, если он есть
                    cur = self.connection.execute(
                        'SELECT city_id '
                        'FROM  zipcode '
                        'WHERE zip_code = ? ',
                        (zip_code,),
                    )
                    zip_code_result = cur.fetchone()
                    # Если результат в базе данных есть по данному zipcode, но
                    # city_id не равен значению в базе, то -> 403
                    if zip_code_result and zip_code_result["city_id"] != city_id:
                        raise sqlite3.IntegrityError
                    # Записываем данные в таблицу zipcode, либо игнорируем, если такое
                    # сочетание zipcode и city_id есть
                    zipcode_query = '''
                        INSERT OR IGNORE INTO zipcode (zip_code, city_id)
                        VAlUES (?, ?) 
                    '''
                    self.connection.execute(zipcode_query, (zip_code, city_id))

            # Работа с таблицей seller и zipcode, если seller false
            else:
                # Получение id объявлений, id машин продавца по id пользователя
                cur = self.connection.execute(
                    'SELECT ad.id as ad_id, ad.car_id '
                    'FROM  ad '
                        'JOIN seller ON seller.id = ad.seller_id '
                    'WHERE seller.account_id = ? ',
                    (user_id,),
                )
                result_ad = cur.fetchall()

                # Удаление продавца по id пользователя
                self.connection.execute(
                    'DELETE FROM seller '
                    'WHERE account_id = ? ',
                    (user_id,),
                )

                # Удаление всех объявлений и всех его связей
                for row in result_ad:
                    ad_id, car_id = dict(row).values()
                    # Удаление объявления, машины, связей по цветам, изображениям и тегам
                    service = AdsService(self.connection)
                    service.delete_ad(ad_id, car_id)

            # Получаем email пользователя по id пользователя
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
        # Структуризация данных продавца и его адресных данных
        seller = ['phone', 'zip_code', 'street', 'home']
        zipcode = ['zip_code', 'city_id']
        seller_dict = {key: value for key, value in request.items()
                       if key in seller}
        zipcode_dict = {key: value for key, value in request.items()
                        if key in zipcode}

        # Если данные переданы, все 4 параметра, то записываем данные в таблицу seller
        if seller_dict and len(seller_dict) == 4:
            seller_params = ', '.join([*seller_dict.keys(), "account_id"])
            seller_query = f'''
                INSERT INTO seller ({seller_params})
                VAlUES (?, ?, ?, ?, ?)
            '''
            self.connection.execute(seller_query, (*seller_dict.values(), user_id))
        # Иначе конфликт -> 403
        else:
            raise sqlite3.IntegrityError

        # Работа с таблицей zipcode
        zip_code = request.get('zip_code')
        city_id = request.get('city_id')
        # Получение данных по zipcode и city_id в таблице zipcode на случай,
        # если они записаны
        cur = self.connection.execute(
            'SELECT * '
            'FROM  zipcode '
            'WHERE zip_code = ? ',
            (zip_code,),
        )
        zip_code_result = cur.fetchone()
        # Если результат в базе данных есть по данному zipcode, но нет city_id в
        # переданных параметрах, то присваиваем значение, полученное из выборки
        if zip_code_result and city_id is None:
            zipcode_dict["city_id"] = zip_code_result["city_id"]
        # Если результат в базе данных есть по данному zipcode, но
        # city_id не равен значению в базе, то -> 403
        if zip_code_result and dict(zip_code_result) != zipcode_dict:
            raise sqlite3.IntegrityError
        # Если имеем 2 параметра, записываем данные в таблицу zipcode,
        # либо игнорируем, если такое сочетание zipcode и city_id есть
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
        # Если нет значения поля, и тип поля не bool для каждого поля из списка,
        # то вернуть True
        for value in request.values():
            if not value and not isinstance(value, bool):
                return True
