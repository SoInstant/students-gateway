from flask import (
    Flask,
    request,
    make_response,
    render_template,
    session,
    redirect,
    url_for,
    flash,
)
import helper
import datetime
from time import time, mktime
from bson.json_util import dumps

app = Flask(__name__)
app.secret_key = "asdfjbkl;oghfj"


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
        if result := helper.authenticate(request.form["username"],
                                         request.form["password"]):
            if result[1] == "admin":
                session["logged_in"] = request.form["username"]
                flash("Successfully logged in!", "info")
                return redirect(url_for("admin"))
            else:
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
        post["date_created"] = datetime.datetime\
            .fromtimestamp(int(post["date_created"])).strftime("%Y-%m-%d %H:%M:%S")
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
        post["date_due"] = datetime.datetime\
            .fromtimestamp(post["date_due"]).strftime("%Y-%m-%d")
    else:
        post["date_due"] = ""
    return render_template("posts_view.html", post=post, username=session["logged_in"])


@app.route("/posts/edit", methods=["POST"])
def posts_edit():
    # request.form...
    # if success
    flash("Successfully edited!", "info")
    return redirect(url_for("posts_view", id=request.args.get("id")))


@app.route("/posts/create", methods=["GET", "POST"])
def posts_create():
    if request.method == "POST":
        if not check_authentication():
            flash("You were logged out, try again!", "error")
            return redirect(url_for("login"))

        # request.form["groups"]
        if request.form["date_due"] != "":
            date_due = int(datetime.datetime.strptime(
                request.form["date_due"], "%Y-%m-%d").timestamp())
        else:
            date_due = None
        status = helper.create_post(session["logged_in"], {
            "title": request.form["title"],
            "body": request.form["body"],
            "group_id": request.form["groups"],
            "requires_acknowledgement": "acknowledgement" in request.form,
            "location": None if request.form["location"] == ""
            else request.form["location"],
            "date_due": date_due
        })
        if status[0]:
            flash("Successfully posted!", "info")
        else:
            flash(f"An error occured: {status[1]}", "error")
        return redirect(url_for("admin"))
    return render_template("posts_create.html", username=session["logged_in"])


@app.route("/api/auth/", methods=["POST"])
def authenticate():
    params = request.json
    if params:
        if params["key"]:
            if params["key"] == "students-gateway-admin":
                status = helper.authenticate(
                    params["username"], params["password"])
                if status:
                    return make_response(
                        dumps(
                            {
                                "auth": True,
                                "user_type": status[1],
                                "message": "User authenticated",
                            }
                        ),
                        200,
                    )
                else:
                    return make_response(
                        dumps({"auth": False, "message": "User not authenticated"}),
                        403,
                    )
            else:
                return make_response(dumps({"message": "Incorrect API key"}), 401)
        else:
            return make_response(dumps({"message": "No API key"}), 400)
    else:
        return make_response(dumps({"message": "No params provided"}), 400)


@app.route("/api/posts/home", methods=["GET"])
def view_posts():
    time_received = time()
    username = request.args.get("username")
    page = request.args.get("page")
    todo = request.args.get("todo")
    try:
        page = int(page)
        todo = bool(int(todo))
    except:
        return "Why are you even trying?"
    if username and page:
        data = helper.get_posts(username, int(page), todo)
        print(f"Time taken: {time() - time_received}")
        return dumps({"data": data})
    else:
        return "Please provide all of the arguments required."


@app.route("/api/autocomplete", methods=["GET"])
def autocomplete():
    query_string = request.args.get("term")
    username = request.args.get("username")
    if query_string and username:
        return dumps(helper.get_group_suggestions(username, query_string))
    else:
        return "No query string/username provided"


if __name__ == "__main__":
    app.run(port=80, debug=True)
