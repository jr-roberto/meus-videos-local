from flask import (
    Blueprint,
    render_template
)

web = Blueprint(
    name="web",
    import_name=__name__,
    url_prefix="/"
)

@web.route("/")
def index():
    return render_template("web/video_processor.html")