import sqlite3
from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)
from flask.views import MethodView

from database import db

bp = Blueprint('colors', __name__)


class ColorsView(MethodView):
    def get(self):
        # Если пользователь не авторизован -> 403
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        # Если авторизованный пользователь не является продавцом -> 403
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

        # Получение списка цветов
        con = db.connection
        cur = con.execute(
            'SELECT * '
            'FROM  color '
        )
        result_colors = cur.fetchall()
        colors = [dict(row) for row in result_colors]
        return jsonify(colors)

    def post(self):
        # Если пользователь не авторизован -> 403
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        # Если авторизованный пользователь не является продавцом -> 403
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

        # Проверка заполнены ли переданные поля, иначе -> 400
        request_json = request.json
        for value in request_json.values():
            if not value:
                return '', 400

        color = request_json.get("name")

        # Проверка наличия цвета в таблице цветов
        cur = con.execute(
            'SELECT * '
            'FROM  color '
            'WHERE color.name = ?',
            (color,),
        )
        result_color = cur.fetchone()

        # Если цвета нет, запись в таблицу color
        if result_color is None:
            try:
                cur = con.execute(
                    'INSERT INTO color (name, hex) '
                    'VALUES (?, ?)',
                    (*request_json.values(),),
                )
                color_id = cur.lastrowid
                con.commit()

            except sqlite3.IntegrityError:
                return '', 409

            return jsonify({"id": color_id, **request_json}), 200

        return jsonify(dict(result_color)), 200


bp.add_url_rule('', view_func=ColorsView.as_view('colors'))