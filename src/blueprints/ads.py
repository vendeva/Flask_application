import sqlite3
import time
from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)
from flask.views import MethodView

from database import db


bp = Blueprint('ads', __name__)


def check_fields(request):
    for key, value in request.items():
        if not value and "num_owners" not in key:
            return True



class AdsView(MethodView):
    def get(self):
        request_args = request.args
        request_one_args = {key: value for key, value in request_args.items()
                if "tags" not in key}

        tags = request_args.get('tags')

        con = db.connection
        params_list = [f'{key} = ?' for key in request_one_args.keys()]

        if tags:
            tags_params = ("','").join(request_args.get('tags').split(','))
            tags_list = f"tag.name IN ('{tags_params}')"
            params_list = [*params_list, tags_list]
        ads_params = ' AND '.join(params_list)

        ads_query = f'''
            SELECT ad.id, seller_id, ad.title, ad.date, car.id as car_id, make, 
                model, mileage, num_owners, reg_number
            FROM  ad
                JOIN car ON car.id = ad.car_id
                JOIN adtag ON adtag.ad_id = ad.id
                JOIN tag ON tag.id = adtag.tag_id                
            WHERE {ads_params} '''

        cur = con.execute(ads_query, (*request_one_args.values(),))
        database_ads = cur.fetchall()

        result = {}
        for row in database_ads:
            id, seller_id, title, date, car_id, make, model, \
            mileage, num_owners, reg_number = dict(row).values()
            if not id in result:
                color_query = f'''
                    SELECT color.id, color.name, hex
                    FROM color
                        JOIN carcolor ON color.id = carcolor.color_id
                    WHERE carcolor.car_id = ?
                    '''
                cur_color = con.execute(color_query, (car_id,))
                result_color = cur_color.fetchall()
                colors = [dict(row) for row in result_color]

                image_query = f'''
                    SELECT image.id, title, url
                    FROM image
                        JOIN car ON car.id = image.car_id
                    WHERE image.car_id = ?
                    '''
                cur_image = con.execute(image_query, (car_id,))
                result_image = cur_image.fetchall()
                images = [dict(row) for row in result_image]

                tag_query = f'''
                    SELECT tag.name as tag_name
                    FROM tag
                        JOIN adtag ON adtag.tag_id = tag.id
                    WHERE adtag.ad_id = ? 
                    '''
                cur_tag = con.execute(tag_query, (id,))
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

        return jsonify([*result.values()])


    def post(self):
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        con = db.connection
        cur = con.execute(
            'SELECT seller.id '
            'FROM  seller '
            'WHERE seller.account_id = ?',
            (session_id,),
        )
        seller = cur.fetchone()
        if seller is None:
            return '', 403

        request_json = request.json
        if check_fields(request_json):
            return '', 400
        if check_fields(request_json.get("car")):
            return '', 400
        for item in request_json.get("car").get('images'):
            if check_fields(item):
                return '', 400

        title = request_json.get("title")
        tags = request_json.get("tags")
        colors = request_json.get("car").get("colors")
        images = request_json.get("car").get("images")
        car = ['make', 'model', 'mileage', 'num_owners', 'reg_number']

        car_values = [value for key, value in request_json.get("car").items()
                    if key in car]


        try:
            cur = con.execute(
                'INSERT INTO car (make, model, mileage, num_owners, reg_number) '
                'VALUES (?, ?, ?, ?, ?)',
                (car_values),
            )
            car_id = cur.lastrowid
            seller_id = seller["id"]
            date = time.time()

            cur = con.execute(
                'INSERT INTO ad (title, seller_id, car_id, date) '
                'VALUES (?, ?, ?, ?)',
                (title, seller_id, car_id, date),
            )

            ad_id = cur.lastrowid

            for color_id in colors:
                con.execute(
                    'INSERT INTO carcolor (car_id, color_id) '
                    'VALUES (?, ?)',
                    (car_id, color_id),
                )

            color_params = (",").join(map(str, colors))
            cur_color = con.execute(f'''
                SELECT id, color.name, hex
                FROM color
                WHERE color.id IN ({color_params})
            ''')
            result_color = cur_color.fetchall()
            color_response = [dict(row) for row in result_color]

            for image in images:
                con.execute(
                    'INSERT INTO image (title, url, car_id) '
                    'VALUES (?, ?, ?)',
                    (*image.values(), car_id),
                )

            tags_params = ("','").join(tags)
            cur_tag = con.execute(f'''
                SELECT id
                FROM tag 
                WHERE tag.name IN ('{tags_params}')            
            ''')
            result_tag = cur_tag.fetchall()

            for row in result_tag:
                tag_id = row["id"]
                con.execute(
                    'INSERT INTO adtag (tag_id, ad_id) '
                    'VALUES (?, ?)',
                    (tag_id, ad_id),
                )

            con.commit()
        except sqlite3.IntegrityError:
            return '', 409


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

        return jsonify(result), 201


class AdView(MethodView):
    def get(self, ad_id):
        con = db.connection
        ads_query = f'''
            SELECT ad.id, seller_id, ad.title, ad.date, car.id as car_id, make, 
                model, mileage, num_owners, reg_number
            FROM  ad
                JOIN car ON car.id = ad.car_id
                JOIN seller ON seller.id = ad.seller_id 
            WHERE ad.id = {ad_id}'''

        cur = con.execute(ads_query)
        result_ad = cur.fetchone()
        if result_ad is None:
            return '', 404

        id, seller_id, title, date, car_id, make, model, \
        mileage, num_owners, reg_number = dict(result_ad).values()

        color_query = f'''
                    SELECT color.id, color.name, hex
                    FROM color
                        JOIN carcolor ON color.id = carcolor.color_id
                    WHERE carcolor.car_id = ?
                    '''
        cur_color = con.execute(color_query, (car_id,))
        result_color = cur_color.fetchall()
        colors = [dict(row) for row in result_color]

        image_query = f'''
                    SELECT image.id, title, url
                    FROM image
                        JOIN car ON car.id = image.car_id
                    WHERE image.car_id = ?
                    '''
        cur_image = con.execute(image_query, (car_id,))
        result_image = cur_image.fetchall()
        images = [dict(row) for row in result_image]

        tag_query = f'''
                    SELECT tag.name as tag_name
                    FROM tag
                        JOIN adtag ON adtag.tag_id = tag.id
                    WHERE adtag.ad_id = ? 
                    '''
        cur_tag = con.execute(tag_query, (id,))
        result_tag = cur_tag.fetchall()
        tags = [row["tag_name"] for row in result_tag]

        result = {
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

        return jsonify(result), 200

    def patch(self, ad_id):
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        con = db.connection
        cur = con.execute(
            'SELECT seller.account_id, ad.car_id '
            'FROM ad '
                'JOIN seller ON ad.seller_id = seller.id '
            'WHERE ad.id = ? ',
            (ad_id,),
        )
        ad = cur.fetchone()
        if ad is None:
            return '', 404

        if ad["account_id"] != session_id:
            return '', 403

        request_json = request.json
        if check_fields(request_json):
            return '', 400

        car_id = ad["car_id"]

        car = ['make', 'model', 'mileage', 'num_owners', 'reg_number']
        car_dict = {key: value for key, value in request_json.get("car").items()
                        if key in car}
        ad_dict = {key: value for key, value in request_json.items()
                        if key in "title"}
        tags = request_json.get("tags")
        colors = request_json.get("car").get("colors")
        images = request_json.get("car").get("images")


        try:

            car_params = ','.join(f'{key} = ?' for key in car_dict.keys())
            car_query = f'UPDATE car SET {car_params} WHERE id = ?'
            con.execute(car_query, (*car_dict.values(), car_id))

            ad_params = ','.join(f'{key} = ?' for key in ad_dict.keys())
            ad_query = f'UPDATE ad SET {ad_params} WHERE id = ?'
            con.execute(ad_query, (*ad_dict.values(), ad_id))

            color_response = []
            if colors:
                con.execute(
                    'DELETE FROM carcolor '
                    'WHERE car_id = ? ',
                    (car_id,),
                )
                for color_id in colors:
                    con.execute(
                        'INSERT INTO carcolor (car_id, color_id) '
                        'VALUES (?, ?)',
                        (car_id, color_id),
                    )
                color_params = (",").join(map(str, colors))
                cur_color = con.execute(f'''
                            SELECT id, color.name, hex
                            FROM color
                            WHERE color.id IN ({color_params})
                        ''')
                result_color = cur_color.fetchall()
                color_response = [dict(row) for row in result_color]

            if images:
                con.execute(
                    'DELETE FROM image '
                    'WHERE car_id = ? ',
                    (car_id,),
                )
                for image in images:
                    con.execute(
                        'INSERT INTO image (title, url, car_id) '
                        'VALUES (?, ?, ?)',
                        (*image.values(), car_id),
                    )


            if tags:
                con.execute(
                    'DELETE FROM adtag '
                    'WHERE ad_id = ? ',
                    (ad_id,),
                )
                tags_params = ("','").join(tags)
                cur_tag = con.execute(f'''
                            SELECT id
                            FROM tag 
                            WHERE tag.name IN ('{tags_params}')            
                        ''')
                result_tag = cur_tag.fetchall()

                for row in result_tag:
                    tag_id = row["id"]
                    con.execute(
                        'INSERT INTO adtag (ad_id, tag_id) '
                        'VALUES (?, ?)',
                        (ad_id, tag_id),
                    )

            con.commit()
        except sqlite3.IntegrityError:
            return '', 409

        car = request_json.get("car")
        car["colors"] = color_response

        return jsonify(request_json), 200

    def delete(self, ad_id):
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        con = db.connection
        cur = con.execute(
            'SELECT seller.account_id, ad.car_id '
            'FROM ad '
                'JOIN seller ON ad.seller_id = seller.id '
            'WHERE ad.id = ? ',
            (ad_id,),
        )
        result_ad_seller = cur.fetchone()
        if result_ad_seller  is None:
            return '', 404

        if result_ad_seller["account_id"] != session_id:
            return '', 403

        car_id = result_ad_seller["car_id"]

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

        return '', 204




bp.add_url_rule('', view_func=AdsView.as_view('ads'))
bp.add_url_rule('/<int:ad_id>', view_func=AdView.as_view('ad'))


