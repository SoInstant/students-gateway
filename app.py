# pylint: disable=missing-module-docstring,missing-function-docstring
import os
import datetime
from time import time

from bson import ObjectId
from bson.json_util import dumps
from flask import (
    Flask,
    request,
    make_response,
    render_template,
    session,
    redirect,
    url_for,
    flash,
    Response,
)

import helper

app = Flask(__name__)
if os.path.isfile(".env"):  # for local testing
    from dotenv import load_dotenv

    load_dotenv(verbose=True)
    app.secret_key = os.getenv("SECRET_KEY")
else:
    app.secret_key = os.environ["SECRET_KEY"]


def check_authentication() -> bool:
    """Checks whether current session is authenticated

    Returns:
        bool: Whether session is authenticated
    """
    if not session.get("logged_in"):
        return False
    return True


@app.route("/")
def index():
    if check_authentication():
        return redirect(url_for("admin"))

    return render_template("index.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if check_authentication():
        return redirect(url_for("admin"))

    if request.method == "POST":
        if result := helper.authenticate(request.form["username"], request.form["password"]):
            if result[0]:  # Successful
                if result[1] == "admin":
                    session["logged_in"] = request.form["username"]
                    flash("Successfully logged in!", "info")
                    return redirect(url_for("admin"))
                print(result[1])
                flash("Students: Please use the mobile app!", "error")
            else:
                flash("Incorrect username/password!", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in")
    flash("Successfully logged out!", "info")
    return redirect(url_for("index"))


@app.route("/admin")
def admin():
    page = int(request.args.get("page", 1))
    if query := request.args.get("query"):  # Query
        posts = helper.search_for_post(session["logged_in"], query, page)
    else:  # All posts
        posts = helper.get_posts(session["logged_in"], page, 0)

    for post in posts:
        post["date_created"] = datetime.datetime.fromtimestamp(
            int(post["date_created"]) + 28800
        ).strftime("%Y-%m-%d %H:%M:%S")
        if len(post["body"]) > 100:  # Trim long descriptions
            post["body"] = post["body"][:100] + "..."

    if page != 1 and len(posts) == 0:
        flash("No more posts to load!", "info")
        page -= 1
        return redirect(url_for("admin", page=page, query=query))

    return render_template("admin.html", posts=posts, page=page, query=query)


@app.route("/posts/view")
def posts_view():
    if post_id := request.args.get("id"):
        post = helper.get_post(post_id)
    else:
        flash("Error: No post ID specified!", "error")
        return redirect(url_for("admin"))
    if post["date_due"]:
        post["date_due"] = datetime.datetime.fromtimestamp(post["date_due"]).strftime("%Y-%m-%d")
    else:
        post["date_due"] = ""
    return render_template("posts_view.html", post=post, username=session["logged_in"])


@app.route("/posts/download")
def posts_download():
    post_id = request.args.get("id")

    if post_id is None:
        return "Missing params"

    return Response(
        helper.download_post(post_id).to_csv(index=False),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={post_id}.csv"},
    )


@app.route("/posts/edit", methods=["POST"])
def posts_edit():
    if not check_authentication():
        flash("You were logged out, try again!", "error")
        return redirect(url_for("login"))

    if request.form["date_due"] != "":
        date_due = int(datetime.datetime.strptime(request.form["date_due"], "%Y-%m-%d").timestamp())
    else:
        date_due = None

    post_id = request.args.get("id")
    if post_id is None:
        flash("Missing parameters", "error")
        return redirect(url_for("posts_view"))

    status = helper.update_post(
        post_id,
        {
            "title": request.form["title"],
            "body": request.form["body"],
            "group_id": ObjectId(request.form["groups"]),
            "requires_acknowledgement": "acknowledgement" in request.form,
            "location": None if request.form["location"] == "" else request.form["location"],
            "date_due": date_due,
        },
    )

    if status:
        flash("Successfully edited!", "info")
    else:
        flash("An error occurred.", "error")

    return redirect(url_for("posts_view", id=post_id))


@app.route("/posts/delete", methods=["POST"])
def posts_delete():
    deletion = helper.delete_post(request.args.get("id"))
    if deletion:
        flash("Successfully deleted!", "info")
        return redirect(url_for("admin"))
    flash("Deletion unsuccessful. Please try again later.", "info")
    return None


@app.route("/posts/create", methods=["GET", "POST"])
def posts_create():
    if request.method == "POST":
        if not check_authentication():
            flash("You were logged out, try again!", "error")
            return redirect(url_for("login"))

        # request.form["groups"]
        if request.form["date_due"] != "":
            date_due = int(
                datetime.datetime.strptime(request.form["date_due"], "%Y-%m-%d").timestamp()
            )
        else:
            date_due = None
        status = helper.create_post(
            session["logged_in"],
            {
                "title": request.form["title"],
                "body": request.form["body"],
                "group_id": request.form["groups"],
                "requires_acknowledgement": "acknowledgement" in request.form,
                "location": None if request.form["location"] == "" else request.form["location"],
                "date_due": date_due,
            },
        )
        if status[0]:
            flash("Successfully posted!", "info")
        else:
            flash(f"An error occurred: {status[1]}", "error")
        return redirect(url_for("admin"))
    return render_template("posts_create.html", username=session["logged_in"])


@app.route("/groups")
def groups():
    if query := request.args.get("query"):
        groups_ = helper.search_for_group(session["logged_in"], query)
    else:
        groups_ = helper.groups_with_user(session["logged_in"])
    return render_template("groups.html", groups=groups_, query=query)


@app.route("/groups/view")
def groups_view():
    group_id = request.args.get("id")
    if group_id is None:
        flash("Missing id", "error")
        return redirect(url_for("groups"))
    group = helper.get_group(group_id)
    return render_template("groups_view.html", group=group)


@app.route("/groups/create", methods=["GET", "POST"])
def groups_create():
    if request.method == "POST":
        if not check_authentication():
            flash("You were logged out, try again!", "error")
            return redirect(url_for("login"))

        owners = [owner.strip() for owner in request.form["owners"].splitlines()]
        members = [member.strip() for member in request.form["members"].splitlines()]

        if helper.create_group(owners, request.form["name"], members):
            flash("Successfully created!", "info")
        else:
            flash("An error occurred!", "error")
        return redirect(url_for("groups"))
    return render_template("groups_create.html", you=session["logged_in"])


@app.route("/groups/edit", methods=["POST"])
def groups_edit():
    if not check_authentication():
        flash("You were logged out, try again!", "error")
        return redirect(url_for("login"))

    group_id = request.args.get("id")
    if group_id is None:
        flash("Missing parameters", "error")
        return redirect(url_for("groups"))

    owners = [owner.strip() for owner in request.form["owners"].splitlines()]
    members = [member.strip() for member in request.form["members"].splitlines()]

    status = helper.update_group(
        group_id, {"name": request.form["name"], "owners": owners, "members": members}
    )
    if status:
        flash("Successfully edited!", "info")
    else:
        flash("An error occurred!", "error")

    return redirect(url_for("groups_view", id=group_id))


@app.route("/groups/delete", methods=["POST"])
def groups_delete():
    group_id = request.args.get("id")
    if group_id is None:
        flash("Missing params", "error")

    if helper.delete_group(group_id):
        flash("Successfully deleted!", "info")
    else:
        flash("An error occurred!", "error")
    return redirect(url_for("groups"))


@app.route("/api/auth/", methods=["POST"])
def authenticate():
    params = request.json
    if params:
        if params["key"]:
            if params["key"] == "students-gateway-admin":
                status = helper.authenticate(params["username"], params["password"])
                if status:
                    return make_response(
                        dumps(
                            {"auth": True, "user_type": status[1], "message": "User authenticated",}
                        ),
                        200,
                    )
                return make_response(
                    dumps({"auth": False, "message": "User not authenticated"}), 403
                )
            return make_response(dumps({"message": "Incorrect API key"}), 401)
        return make_response(dumps({"message": "No API key"}), 400)
    return make_response(dumps({"message": "No params provided"}), 400)


@app.route("/api/users/setExpoPushToken")
def api_users_setexpopushtoken():
    username = request.args.get("username")
    push_token = request.args.get("push_token")
    if helper.set_expo_push_token(username, push_token):
        return make_response(dumps({"message": "Success"}), 200)
    return make_response(dumps({"message": "An error occurred"}), 400)


@app.route("/api/posts/home", methods=["GET"])
def api_posts_home():
    time_received = time()
    username = request.args.get("username")
    page = request.args.get("page")
    todo = request.args.get("todo")
    try:
        page = int(page)
        todo = bool(int(todo))
    except (ValueError, TypeError):
        return "Why are you even trying?"
    if username and page:
        data = helper.get_posts(username, int(page), todo)
        print(f"Time taken: {time() - time_received}")
        return dumps({"data": data})
    return "Please provide all of the arguments required."


@app.route("/api/posts/view")
def api_posts_view():
    username = request.args.get("username")
    post_id = request.args.get("id")
    if username is None or post_id is None:
        return make_response(dumps({"message": "Missing parameters"}), 400)
    if helper.view_post(username, post_id):
        return make_response(dumps({"message": "Success"}), 200)
    return make_response(dumps({"message": "An error occurred"}), 400)


@app.route("/api/posts/respond")
def api_posts_respond():
    username = request.args.get("username")
    post_id = request.args.get("id")
    response = request.args.get("response")
    if username is None or post_id is None or response is None:
        return make_response(dumps({"message": "Missing parameters"}), 400)
    response = True if response == "true" else False  # pylint: disable=R1719
    if helper.respond_post(username, post_id, response):
        return make_response(dumps({"message": "Success"}), 200)
    return make_response(dumps({"message": "An error occurred"}), 400)


@app.route("/api/autocomplete", methods=["GET"])
def autocomplete():
    query_string = request.args.get("term")
    username = request.args.get("username")
    if query_string and username:
        return dumps(helper.search_for_group(username, query_string, suggestion=True))
    return "No query string/username provided"


if __name__ == "__main__":
    app.run(port=80, debug=True)
