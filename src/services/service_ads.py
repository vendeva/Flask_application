import time
import sqlite3
from flask import (
    request,
)
from exceptions import ServiceError


class AdForbiddenError(ServiceError):
    pass

class AdBadRequestError(ServiceError):
    pass

class AdDoesNotExistError(ServiceError):
    pass

class AdIntegrityError(ServiceError):
    pass


class AdsService:
    def __init__(self, connection):
        self.connection = connection

    def get_ads(self, user_id=None):
        request_args = request.args

        # Все параметры кроме tags
        request_one_args = {key: value for key, value in request_args.items()
                if "tags" not in key}
        params_list = [f'{key} = ?' for key in request_one_args.keys()]

        # Добавляем теги в параметры запроса
        tags = request_args.get('tags')
        if tags:
            tags_params = ("','").join(request_args.get('tags').split(','))
            tags_list = f"tag.name IN ('{tags_params}')"
            params_list = [*params_list, tags_list]

        # Добавляем пользователя если он есть в параметры запроса
        if user_id is not None:
            params_list = [*params_list, "seller.account_id = ?"]

        # Составляем строку запроса в базу
        ads_params = ""
        if params_list:
            ads_params = f"WHERE {' AND '.join(params_list)}"
        ads_query = f'''
            SELECT ad.id, seller_id, ad.title, ad.date, car.id as car_id, make, 
                model, mileage, num_owners, reg_number
            FROM  ad
                JOIN car ON car.id = ad.car_id
                JOIN adtag ON adtag.ad_id = ad.id
                JOIN tag ON tag.id = adtag.tag_id
                JOIN seller ON seller.id = ad.seller_id 
            {ads_params}
        '''

        # Составляем список значений параметров в базу
        ads_values = (*request_one_args.values(),)
        if user_id is not None:
            ads_values = (*request_one_args.values(), user_id)
        cur = self.connection.execute(ads_query, (ads_values))
        database_ads = cur.fetchall()

        return self.modify_result_for_get_ads(database_ads)


    def get_ad(self, ad_id):
        # Составляем строку запроса в базу, выборка по id объявления
        ads_query = f'''
               SELECT ad.id, seller_id, ad.title, ad.date, car.id as car_id, make, 
                   model, mileage, num_owners, reg_number
               FROM  ad
                   JOIN car ON car.id = ad.car_id
                   JOIN seller ON seller.id = ad.seller_id 
               WHERE ad.id = {ad_id}
           '''

        cur = self.connection.execute(ads_query)
        result_ad = cur.fetchall()

        # Если объявление не найдено -> 404
        if result_ad is None:
            raise AdDoesNotExistError

        return self.modify_result_for_get_ads(result_ad)


    def post_ads(self, session_id):
        # Проверка является ли пользователь  продавцом, иначе -> 403
        cur = self.connection.execute(
            'SELECT seller.id '
            'FROM  seller '
            'WHERE seller.account_id = ?',
            (session_id,),
        )
        seller = cur.fetchone()
        if seller is None:
            raise AdForbiddenError

        # Проверка заполнены ли необходимые поля (рекурсивно), иначе -> 400
        request_json = request.json
        if self.is_empty_field(request_json):
            raise AdBadRequestError

        # Структуризация исходных данных
        title = request_json.get("title")
        tags = request_json.get("tags")
        car_request = request_json.get("car")
        colors = car_request.get("colors")
        images = car_request.get("images")
        car = ['make', 'model', 'mileage', 'num_owners', 'reg_number']
        car_dict = {key: value for key, value in car_request.items()
                    if key in car}


        try:
            # Запись в таблицу car
            car_params = ', '.join(car_dict.keys())
            car_query = f'''
                INSERT INTO car ({car_params}) 
                VALUES (?, ?, ?, ?, ?)'''
            cur = self.connection.execute(car_query, (*car_dict.values(),))
            car_id = cur.lastrowid

            # Запись в таблицу seller
            seller_id = seller["id"]
            date = time.time()
            cur = self.connection.execute(
                'INSERT INTO ad (title, seller_id, car_id, date) '
                'VALUES (?, ?, ?, ?)',
                (title, seller_id, car_id, date),
            )
            ad_id = cur.lastrowid

            # Запись в таблицу carcolor
            for color_id in colors:
                self.connection.execute(
                    'INSERT INTO carcolor (car_id, color_id) '
                    'VALUES (?, ?)',
                    (car_id, color_id),
                )
            # Выборка необходимых цветов из таблицы color
            color_params = (",").join(map(str, colors))
            cur_color = self.connection.execute(f'''
                SELECT id, color.name, hex
                FROM color
                WHERE color.id IN ({color_params})
            ''')
            result_color = cur_color.fetchall()
            color_response = [dict(row) for row in result_color]

            # Запись в таблицу image
            for image in images:
                self.connection.execute(
                    'INSERT INTO image (title, url, car_id) '
                    'VALUES (?, ?, ?)',
                    (*image.values(), car_id),
                )

            # Получение id тегов из таблицы tag по параметрам запроса
            tags_params = ("','").join(tags)
            cur_tag = self.connection.execute(f'''
                SELECT id
                FROM tag 
                WHERE tag.name IN ('{tags_params}')            
            ''')
            # Запись в таблицу adtag необходимых тегов
            result_tag = cur_tag.fetchall()
            for row in result_tag:
                tag_id = row["id"]
                self.connection.execute(
                    'INSERT INTO adtag (tag_id, ad_id) '
                    'VALUES (?, ?)',
                    (tag_id, ad_id),
                )


            self.connection.commit()

        except sqlite3.IntegrityError:
            raise AdIntegrityError


        car = request_json.get("car")
        car["colors"] = color_response
        result = {
            "id": ad_id,
            "seller_id": seller_id,
            "title": title,
            "date": date,
            "tags": tags,
            "car": car
        }

        return result



    def patch_ad(self, ad_id, car_id):
        # Проверка заполнены ли необходимые поля (рекурсивно), иначе -> 400
        request_json = request.json
        if self.is_empty_field(request_json):
            raise AdBadRequestError

        # Структуризация исходных данных
        car = ['make', 'model', 'mileage', 'num_owners', 'reg_number']
        car_request = request_json.get("car")
        tags = request_json.get("tags")
        car_dict, colors, images = [{}, [], []]
        if car_request is not None:
            colors = car_request.get("colors")
            images = car_request.get("images")
            car_dict = {key: value for key, value in car_request.items()
                        if key in car}
        ad_dict = {key: value for key, value in request_json.items()
                   if key in "title"}

        try:
            # Запись в таблицу car, если переданы параметры
            car_params = ','.join(f'{key} = ?' for key in car_dict.keys())
            if car_params:
                car_query = f'UPDATE car SET {car_params} WHERE id = ?'
                self.connection.execute(car_query, (*car_dict.values(), car_id))

            # Запись в таблицу ad, если переданы параметры
            ad_params = ','.join(f'{key} = ?' for key in ad_dict.keys())
            if ad_params:
                ad_query = f'UPDATE ad SET {ad_params} WHERE id = ?'
                self.connection.execute(ad_query, (*ad_dict.values(), ad_id))

            # Работа с таблицей carcolor, если переданы id цветов
            color_response = []
            if colors:
                # Удаление предыдущих id цветов
                self.connection.execute(
                    'DELETE FROM carcolor '
                    'WHERE car_id = ? ',
                    (car_id,),
                )
                # Запись новых id цветов
                for color_id in colors:
                    self.connection.execute(
                        'INSERT INTO carcolor (car_id, color_id) '
                        'VALUES (?, ?)',
                        (car_id, color_id),
                    )
                # Получение структурированных данных по цветам
                color_params = (",").join(map(str, colors))
                cur_color = self.connection.execute(f'''
                    SELECT id, color.name, hex
                    FROM color
                    WHERE color.id IN ({color_params})
                ''')
                result_color = cur_color.fetchall()
                color_response = [dict(row) for row in result_color]

            # Работа с таблицей image, если переданы данные изображений
            if images:
                # Удаление предыдущих изображений
                self.connection.execute(
                    'DELETE FROM image '
                    'WHERE car_id = ? ',
                    (car_id,),
                )
                # Запись новых изображений
                for image in images:
                    self.connection.execute(
                        'INSERT INTO image (title, url, car_id) '
                        'VALUES (?, ?, ?)',
                        (*image.values(), car_id),
                    )

            # Работа с таблицей image, если переданы данные изображений
            if tags:
                # Удаление предыдущих тегов
                self.connection.execute(
                    'DELETE FROM adtag '
                    'WHERE ad_id = ? ',
                    (ad_id,),
                )
                # Получение id тегов из таблицы tag по параметрам запроса
                tags_params = ("','").join(tags)
                cur_tag = self.connection.execute(f'''
                    SELECT id
                    FROM tag
                    WHERE tag.name IN ('{tags_params}')
                ''')
                # Запись в таблицу adtag необходимых тегов
                result_tag = cur_tag.fetchall()
                for row in result_tag:
                    tag_id = row["id"]
                    self.connection.execute(
                        'INSERT INTO adtag (ad_id, tag_id) '
                        'VALUES (?, ?)',
                        (ad_id, tag_id),
                    )


            self.connection.commit()

        except sqlite3.IntegrityError:
             raise AdIntegrityError

        # Если car_request существует, то перезаписываем параметр colors
        # для требуемого вывода данных
        if car_request is not None:
            car_request["colors"] = color_response

        return request_json


    def delete_ad(self, ad_id, car_id):
        # Удаление объявления, id тегов, машины, изображений и id цветов
        self.connection.executescript(f"""
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


    def is_seller(self, ad_id, session_id):
        # Проверка является ли пользователь продавцом
        cur = self.connection.execute(
            'SELECT seller.account_id, ad.car_id '
            'FROM ad '
            'JOIN seller ON ad.seller_id = seller.id '
            'WHERE ad.id = ? ',
            (ad_id,),
        )
        result_ad_seller = cur.fetchone()
        # Если объявление не найдено -> 404
        if result_ad_seller is None:
            raise AdDoesNotExistError
        # Если пользователь не является продавцом -> 403
        if result_ad_seller["account_id"] != session_id:
            raise AdForbiddenError
        # Возвращаем id машины
        return result_ad_seller["car_id"]


    def is_empty_field(self, request):
        # Проверка полей на пустоту
        for key, value in request.items():
            if not value and "num_owners" not in key:
                return True
            # значение поля словарь и он не пустой рекурсия
            elif value and isinstance(value, dict):
                return self.is_empty_field(value)
            # если поле images, рекурсия элементов списка
            elif value and "images" in key:
                for item in value:
                    return self.is_empty_field(item)



    def modify_result_for_get_ads(self, database_response):
        # Запросы в базу и приведение к необходимому виду полученного результата
        result = {}
        for row in database_response:
            id, seller_id, title, date, car_id, make, model, \
            mileage, num_owners, reg_number = dict(row).values()
            if not id in result:
                # Получение цветов
                color_query = '''
                    SELECT color.id, color.name, hex
                    FROM color
                        JOIN carcolor ON color.id = carcolor.color_id
                    WHERE carcolor.car_id = ?
                '''
                cur_color = self.connection.execute(color_query, (car_id,))
                result_color = cur_color.fetchall()
                colors = [dict(row) for row in result_color]

                # Получение изображений
                image_query = '''
                    SELECT image.id, title, url
                    FROM image
                        JOIN car ON car.id = image.car_id
                    WHERE image.car_id = ?
                '''
                cur_image = self.connection.execute(image_query, (car_id,))
                result_image = cur_image.fetchall()
                images = [dict(row) for row in result_image]

                # Получение тегов
                tag_query = '''
                    SELECT tag.name as tag_name
                    FROM tag
                        JOIN adtag ON adtag.tag_id = tag.id
                    WHERE adtag.ad_id = ? 
                '''
                cur_tag = self.connection.execute(tag_query, (id,))
                result_tag = cur_tag.fetchall()
                tags = [row["tag_name"] for row in result_tag]

                result[id] = {
                    "id": id,
                    "seller_id": seller_id,
                    "title": title,
                    "date": time.strftime("%m/%d/%Y", time.localtime(date)),
                    "tags": tags,
                    "car": {
                        "make": make,
                        "model": model,
                        "colors": colors,
                        "mileage": mileage,
                        "num_owners": num_owners,
                        "reg_number": reg_number,
                        "images": images
                    }
                }

        return [*result.values()]
