# pylint: disable=C0114,C0116
import hashlib
import os
from secrets import token_hex
from time import time

import pymongo
from bson import ObjectId

if os.path.isfile(".env"):
    from dotenv import load_dotenv

    load_dotenv(verbose=True)
    db_username = os.getenv("DB_USERNAME")
    db_password = os.getenv("DB_PASSWORD")
else:
    db_username = os.environ["DB_USERNAME"]
    db_password = os.environ["DB_PASSWORD"]

client = pymongo.MongoClient(
    f"mongodb+srv://{db_username}:{db_password}@cluster0.g9wex.gcp.mongodb.net/"
    f"<dbname>?retryWrites=true&w=majority"
)
db = client["students-gateway"]


# Auth functions
def generate_salt():
    return token_hex(16)


def generate_hash(password, salt):
    string = password + salt
    return hashlib.sha256(string.encode()).hexdigest()


def create_user(username, name, password, user_type):
    col = db["users"]
    salt = generate_salt()
    password_hash = generate_hash(password, salt)
    insert = col.insert_one(
        {
            "username": username,
            "name": name,
            "salt": salt,
            "password_hash": password_hash,
            "user_type": user_type,
        }
    )
    return insert.acknowledged


def create_group(owner_id: list, name: str, members: list):
    col = db["groups"]
    insert = col.insert_one({"name": name, "owner": owner_id, "members": members})
    return insert.acknowledged


def add_user_to_group(group_id: str, user_id: str):
    pass


def authenticate(username, password):
    col = db["users"]
    results = col.find_one({"username": username},
                           {"password_hash": 1, "salt": 1, "user_type": 1})
    if results:
        if generate_hash(password, results["salt"]) == results["password_hash"]:
            return True, results["user_type"]
    else:
        return False, ""


def groups_with_user(username):
    return [
        ObjectId(group["_id"])
        for group in list(
            db["groups"].find(
                {"$or": [{"owner": username}, {"members": username}]}, {"_id": 1})
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
        db["posts"].find(query).sort("date_created", -
                                     1).skip((page - 1) * 5).limit(5)
    )

    for post in user_posts:
        author_name = db["users"].find_one(
            {"username": post["author_id"]})["name"]
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
    # post["group_name"] = group["name"]
    post["acknowledged"] = dict([
        (entry["username"], entry["response"]) for entry in post["acknowledged"]
    ])

    group_members = group["members"]
    responses = {}
    for member in group_members:
        try:
            response = post["acknowledged"][member]
        except KeyError:
            response = None
        responses[member] = {
            "viewed": member in post["viewed"],
            "acknowledged": response,
        }
    post["responses"] = responses

    del post["author_id"], post["viewed"], post["acknowledged"]  # , post["group_id"]
    return post


def view_post(username, post_id):
    """Sets the status of a post to read

    Args:
        username (str): username of user
        post_id (str): post id of the post to be read

    Returns:
        A boolean value indicating if setting the post to read was successful
    """
    col = db["posts"]
    update = col.update_one({"_id": ObjectId(post_id)}, {"$addToSet": {"viewed": username}})
    if update.modified_count:
        col.update_one(
            {"_id": ObjectId(post_id)},
            {"$addToSet": {"acknowledged": {"username": username, "response": None}}},
        )
    return update.modified_count == 1


def respond_post(username, post_id, response):
    """Indicate the response by a user to a post"""
    col = db["posts"]
    update = col.update_one(
        {"_id": ObjectId(post_id), "acknowledged.username": username},
        {"$set": {"acknowledged.$.response": response}},
    )


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
        group_exists = len(list(db["groups"].find(
            {"_id": ObjectId(data["group_id"])})))
        if group_exists:
            date = round(time())
            data["date_created"] = int(date)
            data["author_id"] = username
            data["group_id"] = ObjectId(data["group_id"])
            data["viewed"] = []
            data["acknowledged"] = []
            try:
                insert = db["posts"].insert_one(data)
                return insert.acknowledged, "Post created successfully"
            except pymongo.errors.WriteError:
                return False, "Post was not created successfully"
        else:
            return False, "group_id is invalid"
    else:
        absent_keys = [key for key in compulsory_keys if key not in data.keys()]
        return False, f"Missing keys: {', '.join(absent_keys)}"


def update_post():
    """Updates a post made by an admin"""


def delete_post():
    """Updates a post made by an admin"""


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
    suggestions = col.find({"$text": {"$search": query}, "owner": username},
                           {"_id": 1, "name": 1})
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
    pass
