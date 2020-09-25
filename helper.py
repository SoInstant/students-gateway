# pylint: disable=C0114,C0116
import hashlib
from os import environ as env
from secrets import token_hex
from time import time

import pymongo
from bson import ObjectId

client = pymongo.MongoClient(
    f"mongodb+srv://{env['DB_USERNAME']}:{env['DB_PASSWORD']}@cluster0.g9wex.gcp.mongodb.net/"
    f"<dbname>?retryWrites=true&w=majority "
)
db = client["students-gateway"]


# Auth functions
def generate_salt():
    return token_hex(16)


def generate_hash(password, salt):
    string = password + salt
    return hashlib.sha256(string.encode()).hexdigest()


def authenticate(username, password):
    col = db["users"]
    results = col.find_one({"username": username}, {"password_hash": 1, "salt": 1, "user_type": 1})
    if results:
        if generate_hash(password, results["salt"]) == results["password_hash"]:
            return True, results["user_type"]
    else:
        return False, None


def groups_with_user(username):
    return [
        ObjectId(group["_id"])
        for group in list(
            db["groups"].find({"$or": [{"owner": username}, {"members": username}]}, {"_id": 1})
        )
    ]


# Post functions
def get_posts(username, page, todo):
    """Gets the posts of a user, by page

    Args:
        username (str): username of user
        page (int): page of posts (each page has 5 posts)
        todo (int): 1 to filter by viewed = True, 0 to avoid filter

    Returns:
        A list containing dictionary objects that represent a post
    """
    groups = groups_with_user(username)
    query = {"group_id": {"$in": groups}}
    if todo:
        query["viewed"] = {"$nin": [username]}
    user_posts = list(
        db["posts"].find(query).sort("date_created", -1).skip((page - 1) * 5).limit(5)
    )

    for post in user_posts:
        author_name = db["users"].find_one({"username": post["author_id"]})["name"]
        post["author_name"] = author_name
        group_name = db["groups"].find_one({"_id": post["group_id"]})["name"]
        post["group_name"] = group_name
        post["viewed"] = username in post["viewed"]
        del post["author_id"], post["group_id"]
    return user_posts


def get_post(post_id):
    """Get a singular post, by id

    Args:
        post_id (str): post id of the post to be get

    Returns:
        Dictionary object that represents a post
    """

    post = db["posts"].find_one({"_id": ObjectId(post_id)})
    group = db["groups"].find_one({"_id": post["group_id"]})

    post["author_name"] = db["users"].find_one({"username": post["author_id"]})["name"]
    post["group_name"] = group["name"]

    group_members = group["members"]
    responses = {}
    for member in group_members:
        responses[member] = {
            "viewed": member in post["viewed"],
            "acknowledged": member in post["acknowledged"],
        }
    post["responses"] = responses

    del post["author_id"], post["group_id"], post["viewed"], post["acknowledged"]
    return post


def view_post(username, post_id):
    """Sets the status of a post to read

    Args:
        username (str): username of user
        post_id (str): post id of the post to be read

    Returns:
        A boolean value indicating if the read was successful
    """
    db["posts"]


def respond_post(username, post_id, response):
    """Indicate the response by a user to a post"""
    pass


def create_post(username, data):
    """Creates a post

    Args:
        username (str): username of user making the post
        data (dict): post information in the form of {field:value}.
            Compulsory fields: title (str), body (str), group_id (str), location (str or None),
                requires_acknowledgement (boolean), date_due (integer)

    Returns:
        A tuple containing:
            a boolean value indicating if the post creation was successful;
            a string containing a message giving details on the creation
    """
    compulsory_keys = {
        "title",
        "body",
        "group_id",
        "location",
        "requires_acknowledgement",
        "date_due",
    }
    if compulsory_keys.issubset(set(data.keys())):
        group_exists = len(list(db["groups"].find({"_id": ObjectId(data["group_id"])})))
        if group_exists:
            date = round(time())
            data["date_created"] = int(date)
            data["author_id"] = username
            data["group_id"] = ObjectId(data["group_id"])
            data["viewed"] = []
            data["acknowledged"] = []
            try:
                insert = db["posts"].insert_one(data)
                return (insert.acknowledged, "Post created successfully")
            except pymongo.errors.WriteError:
                return (False, "Post was not created successfully")
        else:
            return (False, "group_id is invalid")
    else:
        absent_keys = [key for key in compulsory_keys if key not in data.keys()]
        return (False, f"Missing keys: {', '.join(absent_keys)}")


def update_post():
    """Updates a post made by an admin"""
    pass


def delete_post():
    """Updates a post made by an admin"""
    pass


def download_posts():
    pass


def get_group_suggestions(username: str, query: str) -> list:
    """Makes suggestions based on query string

    Args:
        username: username of user conducting search
        query: query string

    Returns:
        A list containing dictionaries of suggestions in the form of
        {'label' : group_name, 'value': group_id}
    """
    col = db["groups"]
    suggestions = col.find({"$text": {"$search": query}, "owner": username}, {"_id": 1, "name": 1})
    return [{"label": group["name"], "value": str(group["_id"])} for group in suggestions]


def search_for_post(username: str, query: str, page: int) -> list:
    """Searches for posts containing query string

    Args:
        username: username of user conducting search
        query: query string
        page: page of results to be fetched

    Returns:
        A list that contains the posts that match the query string, which are in dictionary form
    """
    col = db["posts"]
    groups = groups_with_user(username)
    return list(
        col.find({"$text": {"$search": query}, "group_id": {"$in": groups}})
        .sort("date_created", -1)
        .skip((page - 1) * 5)
        .limit(5)
    )


if __name__ == "__main__":
    # salt = generate_salt()
    # print(salt)
    # print(generate_hash("passwd", salt))

    # a = create_post(
    #     "",
    #     {
    #         "title": "",
    #         "body": "",
    #         "group_id": "",
    #     },
    # )
    # print(a)

    # Demonstrate admin
    # print(f"Admin posts: {get_posts('bokai.wu',3,0)}")

    # Demonstrate user
    # print(f"User posts: {get_posts('23ychij199g',3,1)}")

    # print(get_post("5f64d4b9ce2728e80c253488"))
    pass
