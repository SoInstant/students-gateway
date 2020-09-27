# pylint: disable=missing-module-docstring,consider-using-dict-comprehension,fixme
"""Helper functions for app.py

This module provides authentication, posts-related, groups-related, user-related and miscellaneous
functions for app.py.
"""
import hashlib
import os
from secrets import token_hex
from time import time

import pymongo
from bson import ObjectId
import pandas

if os.path.isfile(".env"):  # for local testing
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
    """Generates a 16 byte salt

    Returns:
        A string that representing the 16 byte salt generated
    """
    return token_hex(16)


def generate_hash(password: str, salt: str) -> str:
    """Generates a hash based on a password and salt

    Args:
        password: A string representing the password
        salt: A string representing the 16 byte salt

    Returns:
        A string that representing the salted hash of the password

    Raises:
        ValueError: Salt must be of length 32
    """
    if len(salt) != 32:
        raise ValueError("Salt must be of length 32")
    string = password + salt
    return hashlib.sha256(string.encode()).hexdigest()


def authenticate(username: str, password: str) -> tuple:
    """Authenticates a user

    Args:
        username: A string that represents the username of the user to be authenticated
        password: A string that represents the password of the user to be authenticated

    Returns:
        A tuple containing:
            - a boolean value indicating if the authentication attempt succeeded
            - a string representing the user type. If the authentication attempt failed,
                 the user type will be an empty string.
    """
    col = db["users"]
    results = col.find_one({"username": username}, {"password_hash": 1, "salt": 1, "user_type": 1})
    if results:
        if generate_hash(password, results["salt"]) == results["password_hash"]:
            return True, results["user_type"]
    return False, ""


def create_user(username: str, name: str, password: str, user_type: str) -> bool:
    """Creates a user in the database

    Args:
        username: A string representing the username of the user
        name: A string representing the name of the user
        password: A string representing the password of the user
        user_type: A string with the value 'admin' or 'user' that represents user type of the user

    Returns:
        A boolean value indicating if the creation of the user was successful

    Raise:
        ValueError: user_type must be either 'admin' or 'user'
    """
    if user_type not in ("admin", "user"):
        raise ValueError("user_type must be either 'admin' or 'user'")

    salt = generate_salt()
    password_hash = generate_hash(password, salt)

    col = db["users"]
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


def create_group(owner_id: list, name: str, members: list) -> bool:
    """Creates a group in the database

    Args:
        owner_id: A list containing strings that represent the id(s) of the owner(s)
        name: A string representing the name of the group
        members: A list containing strings that represent the id(s) of the member(s)

    Returns:
        A boolean value indicating if the creation of the group was successful
    """
    col = db["groups"]
    insert = col.insert_one({"name": name, "owners": owner_id, "members": members})
    return insert.acknowledged


def update_group(group_id: str, data: dict) -> bool:
    """Updates a group

    Args:
        group_id: A string containing the group id of the group
        data: A dictionary containing the data to be updated, in the form of {field: value}

    Returns:
        A boolean value indicating if the update was successful
    """
    col = db["groups"]
    update = col.update_one({"_id": ObjectId(group_id)}, data)
    return update.modified_count == 1


def get_group(group_id: str) -> dict:
    """Get a singular group, by id

    Args:
        group_id (str): A string representing the group id of the group to get

    Returns:
        Dictionary object that represents the group
    """
    col = db["groups"]
    return col.find_one({"_id": ObjectId(group_id)})


def groups_with_user(username: str) -> list:
    """Finds group(s) with user in it/them

    Args:
        username: A string representing the username of the user

    Returns:
        A list containing information of groups that user is in
    """
    groups = list(db["groups"].find({"$or": [{"owners": username}, {"members": username}]}))
    for group in groups:
        group["_id"] = ObjectId(group["_id"])
    return groups


# Post functions
def get_posts(username: str, page: int, todo: int) -> list:
    """Gets the posts of a user, by page

    Args:
        username: A string representing the username of the user
        page: An integer representing the page of posts to get (each page has 5 posts)
        todo: An integer that represents if the posts are filtered by viewed
            1 to filter by viewed = True; 0 to avoid filter

    Returns:
        A list containing dictionary objects that represent a post
    """
    groups = [group["_id"] for group in groups_with_user(username)]

    query = {"group_id": {"$in": groups}}
    if todo:
        query["viewed"] = {"$nin": [username]}

    user_posts = list(
        db["posts"].find(query).sort("date_created", -1).skip((page - 1) * 5).limit(5)
    )

    for post in user_posts:
        author_name = db["users"].find_one({"username": post["author_id"]})["name"]
        group_name = db["groups"].find_one({"_id": post["group_id"]})["name"]

        post["author_name"] = author_name
        post["group_name"] = group_name
        post["viewed"] = username in post["viewed"]
        response = None
        if "acknowledged" in post:
            for response_ in post["acknowledged"]:
                if response_["username"] == username:
                    response = response_["response"]
        post["acknowledged"] = response

        del post["author_id"], post["group_id"]
    return user_posts


def get_post(post_id: str) -> dict:
    """Get a singular post, by id

    Args:
        post_id (str): A string representing the post id of the post to get

    Returns:
        Dictionary object that represents the post
    """
    post = db["posts"].find_one({"_id": ObjectId(post_id)})
    if post:
        group = db["groups"].find_one({"_id": post["group_id"]})

        post["author_name"] = db["users"].find_one({"username": post["author_id"]})["name"]
        post["group_name"] = group["name"]
        if post["requires_acknowledgement"]:
            post["acknowledged"] = dict(
                [(entry["username"], entry["response"]) for entry in post["acknowledged"]]
            )

        group_members = group["members"]
        responses = {}
        for member in group_members:
            if post["requires_acknowledgement"]:
                try:
                    response = post["acknowledged"][member]
                except KeyError:
                    response = None
                responses[member] = {
                    "viewed": member in post["viewed"],
                    "acknowledged": response,
                }
            else:
                responses[member] = {
                    "viewed": member in post["viewed"],
                }
        post["responses"] = responses

        del post["author_id"], post["viewed"]
        if post["requires_acknowledgement"]:
            del post["acknowledged"]
        return post
    return {}


def view_post(username: str, post_id: str) -> bool:
    """Sets the status of a post to read

    Args:
        username: A string representing the username of the user
        post_id: A string representing the post id of the post to be set to viewed

    Returns:
        A boolean value indicating if setting the post to viewed was successful
    """
    col = db["posts"]
    update = col.update_one({"_id": ObjectId(post_id)}, {"$addToSet": {"viewed": username}})
    if update.modified_count:
        requires_acknowledgedment = col.find_one({"_id": ObjectId(post_id)})[
            "requires_acknowledgement"
        ]
        if requires_acknowledgedment:
            col.update_one(
                {"_id": ObjectId(post_id)},
                {"$addToSet": {"acknowledged": {"username": username, "response": None}}},
            )
    return update.modified_count == 1


def respond_post(username: str, post_id: str, response: bool):
    """Indicate the response by a user to a post

    Args:
        username: A string representing the username of the user
        post_id: A string representing the post id of the post the user responded to
        response: A boolean value representing the response by the user

    Returns:
        A boolean value indicating if the submitting of the response was successful
    """
    col = db["posts"]
    update = col.update_one(
        {"_id": ObjectId(post_id), "acknowledged.username": username},
        {"$set": {"acknowledged.$.response": response}},
    )
    return update.modified_count == 1


def create_post(username: str, data: dict) -> tuple:
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
                return insert.acknowledged, "Post created successfully"
            except pymongo.errors.WriteError:
                return False, "Post was not created successfully"
        else:
            return False, "group_id is invalid"
    else:
        absent_keys = [key for key in compulsory_keys if key not in data.keys()]
        return False, f"Missing keys: {', '.join(absent_keys)}"


def update_post(post_id: str, data: dict) -> bool:
    """Updates a post made by an admin

    Args:
        post_id: A string representing the post to be updated
        data: A dictionary containing the data to be updated, in the form of {field: value}

    Returns:
        A boolean value indicating if the update was successful
    """
    col = db["posts"]
    update = col.update_one({"_id": ObjectId(post_id)}, data)
    return update.modified_count == 1


def delete_post(post_id: str) -> bool:
    """Deletes a post made by an admin

    Args:
        post_id: A string representing the post id of the post to be deleted

    Returns:
        A boolean value indicating if the deletion of the post was successful
    """
    col = db["posts"]
    delete = col.delete_one({"_id": ObjectId(post_id)})
    return delete.deleted_count == 1


def download_post(post_id):
    """Download the responses to a post

    Args:
        post_id: A string representing the id of the post to be downloaded

    Returns:
        A pandas.DataFrame object that contains the data of the post, with columns "username",
        "viewed" and "response".

        "viewed" contains either '1' or '0':
            '1' indicates that the user has viewed the post
            '0' indicates that the user has not viewed the post

        "response" contains either '1', '0' or '':
            '1' indicates that the user has responded with 'yes' to the post
            '0' indicates that the user has responded with 'no' to the post
            '' indicates that the user has not responded to the post

        For example:
                  username  viewed response
            0  23ychij199g       1        1
            1  23ylohy820c       1
    """
    post = get_post(post_id)
    responses = post["responses"]
    requires_acknowledgement = post["requires_acknowledgement"]
    data = []
    for user, response in responses.items():
        i = [user, int(response["viewed"])]
        if requires_acknowledgement:
            if response["acknowledged"] is None:
                i.append("")
            else:
                i.append(int(response["acknowledged"]))
        data.append(i)
    return pandas.DataFrame.from_records(data, columns=["username", "viewed", "response"])


def search_for_group(username: str, query: str, suggestion=False) -> list:
    """Makes suggestions based on query string

    Args:
        username: A string representing the username of user conducting search
        query: A string representing the query string
        suggestion: A boolean value that indicates whether to provide data in form conducive
            for jquery's autocomplete. Defaults to False

    Returns:
        A list containing dictionaries of suggestions in the form of
        {'label' : group_name, 'value': group_id}
    """
    col = db["groups"]
    groups = col.find({"$text": {"$search": query}, "owners": username}, {"_id": 1, "name": 1})
    if suggestion:
        return [{"label": group["name"], "value": str(group["_id"])} for group in groups]
    return groups


def search_for_post(username: str, query: str, page: int) -> list:
    """Searches for posts containing query string

    Args:
        username: A string representing the username of user conducting search
        query: A string representing the query string
        page: An integer indicating the page of results to be fetched

    Returns:
        A list that contains the posts that match the query string, which are in dictionary form
    """
    col = db["posts"]
    groups = [group["_id"] for group in groups_with_user(username)]
    return list(
        col.find({"$text": {"$search": query}, "group_id": {"$in": groups}})
        .sort("date_created", -1)
        .skip((page - 1) * 5)
        .limit(5)
    )


def set_expo_push_token(username: str, push_token: str) -> bool:
    """Sets Expo's push notifications token for given user

    Args:
        username: A string representing the username of user
        push_token: User's push token

    Returns:
       Whether set is successful
    """
    col = db["users"]
    update = col.update_one({"username": username}, {"$set": {"push_token": push_token}})
    return update.modified_count == 1


if __name__ == "__main__":
    import json

    p_1 = get_post("5f64d4b9ce2728e80c253488")
    p_1["_id"] = str(p_1["_id"])
    p_1["group_id"] = str(p_1["group_id"])
    p_2 = get_post("5f658197dd01a96f34457097")
    p_2["_id"] = str(p_2["_id"])
    p_2["group_id"] = str(p_2["group_id"])
    print(json.dumps(p_1), json.dumps(p_2))
    print(download_post("5f64d4b9ce2728e80c253488"))
