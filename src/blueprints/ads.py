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
    AdIntegrityError,
    AdDoesNotExistError,
)

from database import db


bp = Blueprint('ads', __name__)


class AdsView(MethodView):
    def get(self):
        con = db.connection
        service = AdsService(con)
        ads = service.get_ads()
        return jsonify(ads)


    def post(self):
        session_id = session.get('user_id')
        if session_id is None:
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


class AdView(MethodView):
    def get(self, ad_id):
        con = db.connection
        service = AdsService(con)
        try:
            ads = service.get_ad(ad_id)
        except AdDoesNotExistError:
            return '', 404
        return jsonify(ads)


    def patch(self, ad_id):
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        con = db.connection
        service = AdsService(con)
        try:
            car_id = service.is_seller(ad_id, session_id)
            ads = service.patch_ad(ad_id, car_id)
        except AdDoesNotExistError:
            return '', 404
        except AdForbiddenError:
            return '', 403
        except AdBadRequestError:
            return '', 400
        except AdIntegrityError:
            return '', 409
        else:
            return jsonify(ads), 200


    def delete(self, ad_id):
        session_id = session.get('user_id')
        if session_id is None:
            return '', 403

        con = db.connection
        service = AdsService(con)
        try:
            car_id = service.is_seller(ad_id, session_id)
            service.delete_ad(ad_id, car_id)
        except AdDoesNotExistError:
            return '', 404
        except AdForbiddenError:
            return '', 403
        else:
            return '', 204



bp.add_url_rule('', view_func=AdsView.as_view('ads'))
bp.add_url_rule('/<int:ad_id>', view_func=AdView.as_view('ad'))


