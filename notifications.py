import requests
import json


def notify(push_tokens: list, title: str, body: str):
    """Sends push notifications to specified users' devices

    Args:
        push_tokens: List of users' Expo push tokens
        title: Title of notification
        body: Body of notification

    Returns:
        Whether operation is successful
    """
    r = requests.post(
        "https://exp.host/--/api/v2/push/send",
        data=json.dumps(
            {
                "to": push_tokens,
                "title": title,
                "body": body,
            }
        ),
        headers={
            "host": "exp.host",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",
            "content-type": "application/json",
        },
    )
    print(r.text)
    return r.status_code == 200


if __name__ == "__main__":
    notify(["ExponentPushToken[Jue46jOCu0aDtQ7iMKKERW]"], "New post", "Bitch")