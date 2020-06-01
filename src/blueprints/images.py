import sqlite3
import os
from flask import (
    Blueprint,
    request,
    session,
    current_app,
    url_for,
    redirect,
    send_file
)
from werkzeug.utils import secure_filename
from flask.views import MethodView

from database import db

bp = Blueprint('images', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in current_app.config['ALLOWED_EXTENSIONS']


class ImagesView(MethodView):
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


        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            images_folder = os.path.join(os.path.dirname(__file__), '..',
                  current_app.config['UPLOAD_FOLDER'], filename)
            file.save(images_folder)
            return redirect(url_for("images.image", image_name=filename))


class ImageView(MethodView):
    def get(self, image_name):
        images_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], image_name)
        return send_file(images_folder, mimetype='image/gif')

bp.add_url_rule('', view_func=ImagesView.as_view('images'))
bp.add_url_rule('/<image_name>', view_func=ImageView.as_view('image'))