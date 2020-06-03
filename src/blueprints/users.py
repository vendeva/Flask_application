from flask import (
    Blueprint,
    jsonify,
    session,
)
from flask.views import MethodView
from services.service_user import (
    UserService,
    UserBadRequestError,
    UserIntegrityError,
    UserDoesNotExistError,
)


from database import db


bp = Blueprint('users', __name__)


class UsersView(MethodView):
    def post(self):
        # Если пользователь авторизован -> 403
        session_id = session.get('user_id')
        if session_id:
            return '', 403

        con = db.connection
        service = UserService(con)
        try:
            # Регистрация пользователя
            user = service.post_user()
        except UserBadRequestError:
            return '', 400
        except UserIntegrityError:
            return '', 409
        else:
            return jsonify(user), 201


class UserView(MethodView):
    def get(self, user_id):
        # Если пользователь не авторизован -> 403
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        con = db.connection
        service = UserService(con)
        try:
            # Получение данных пользователя
            user = service.get_user(user_id)
        except UserDoesNotExistError:
            return '', 404
        else:
            return jsonify(user)


    def patch(self, user_id):
        # Если пользователь не авторизован или id в сессии не равно user_id -> 403
        session_id = session.get('user_id')
        if session_id is None or session_id != user_id:
            return '', 403

        con = db.connection
        service = UserService(con)
        try:
            # Редактирование данных пользователя
            user = service.patch_user(user_id)
        except UserDoesNotExistError:
            return '', 404
        except UserBadRequestError:
            return '', 400
        except UserIntegrityError:
            return '', 409
        else:
            return jsonify(user)




bp.add_url_rule('', view_func=UsersView.as_view('users'))
bp.add_url_rule('/<int:user_id>', view_func=UserView.as_view('user'))
