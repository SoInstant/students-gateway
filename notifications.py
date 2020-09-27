"""Notifications functions for app.py

This module provides notifications.
"""
import json
import requests


def notify(push_tokens: list, title: str, body: str):
    """Sends push notifications to specified users' devices

    Args:
        push_tokens: List of users' Expo push tokens
        title: Title of notification
        body: Body of notification

    Returns:
        Whether operation is successful
    """
    request = requests.post(
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
    print(request.text)
    return request.status_code == 200


if __name__ == "__main__":
    notify(
        ["ExponentPushToken[Jue46jOCu0aDtQ7iMKKERW]"],
        "Remedial lessons!",
        "2020 Y3 Biology - Wu Bokai\nPost fcontent........",
    )
