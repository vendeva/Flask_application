import sqlite3
from flask import (
    Blueprint,
    jsonify,
    request,
)
from flask.views import MethodView

from database import db

bp = Blueprint('cities', __name__)


class CitiesView(MethodView):
    def get(self):
        con = db.connection
        cur = con.execute(
            'SELECT * '
            'FROM  city '
        )
        result_cities = cur.fetchall()
        cities = [dict(row) for row in result_cities]
        return jsonify(cities)



    def post(self):
        request_json = request.json
        city = request_json.get("name")
        if not city:
            return '', 400


        con = db.connection
        cur = con.execute(
            'SELECT * '
            'FROM  city '
            'WHERE city.name = ?',
            (city,),
        )
        result_city = cur.fetchone()

        if result_city is None:
            try:
                cur = con.execute(
                    'INSERT INTO city (name) '
                    'VALUES (?)',
                    (city,),
                )

                city_id = cur.lastrowid
                con.commit()
            except sqlite3.IntegrityError:
                return '', 409

            return jsonify({"id": city_id, **request_json}), 200

        return jsonify(dict(result_city)), 200


bp.add_url_rule('', view_func=CitiesView.as_view('cities'))