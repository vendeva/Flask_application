from flask import (
    Blueprint,
    jsonify,
    session,
)
from flask.views import MethodView
from services.service_ads import (
    AdsService,
    AdForbiddenError,
    AdBadRequestError,
    AdIntegrityError
)

from database import db


bp = Blueprint('user_ads', __name__)


class UserAdsView(MethodView):
    def get(self, user_id):
        con = db.connection
        service = AdsService(con)
        ads = service.get_ads(user_id)
        return jsonify(ads)


    def post(self, user_id):
        session_id = session.get('user_id')
        if session_id is None or session_id != user_id:
            return '', 403

        con = db.connection
        service = AdsService(con)
        try:
            ads = service.post_ads(session_id)
        except AdForbiddenError:
            return '', 403
        except AdBadRequestError:
            return '', 400
        except AdIntegrityError:
            return '', 409
        else:
            return jsonify(ads), 201


bp.add_url_rule('/<int:user_id>/ads', view_func=UserAdsView.as_view('user_ads'))
