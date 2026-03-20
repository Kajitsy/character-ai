import os
import json
import base64
import mimetypes

from random import randint
from typing import Any, List, Optional, Union
from urllib.parse import urlparse, quote

from ..types import Avatar, Voice
from ..exceptions import (
    FetchError,
    EditError,
    UploadError,
    SearchError,
    ActionError,
    InvalidArgumentError,
    DeleteError,
)

from ..requester import Requester


class UtilsMethods:
    def __init__(self, client, requester: Requester):
        self.__client = client
        self.__requester = requester

    async def ping(self, **kwargs: Any) -> bool:
        request = await self.__requester.request_async(
            url="https://neo.character.ai/ping/",
            options={"headers": self.__client.get_headers(kwargs.get("token", None))},
        )

        return request.status_code == 200

    async def generate_image(self, prompt: str, **kwargs: Any) -> List[str]:
        num_candidates: int = kwargs.get("num_candidates", 4)

        request = await self.__requester.request_async(
            url="https://plus.character.ai/chat/character/generate-avatar-options",
            options={
                "method": "POST",
                "headers": self.__client.get_headers(kwargs.get("token", None)),
                "body": json.dumps(
                    {
                        "prompt": prompt,
                        "num_candidates": num_candidates,
                        "model_version": "v1",
                    }
                ),
            },
        )

        if request.status_code == 200:
            response = request.json()
            result = response.get("result", [])

            urls = []

            for img in result:
                url = img.get("url", None)
                if url:
                    urls.append(url)

            return urls

        raise ActionError("Cannot generate image.")

    async def upload_avatar(self, image: str, check_image: bool = True, **kwargs: Any) -> Avatar:
        if os.path.isfile(image):
            with open(image, "rb") as image_file:
                data = base64.b64encode(image_file.read())

        else:
            parsed_url = urlparse(image)
            if parsed_url.scheme and parsed_url.netloc:
                image_request = await self.__requester.request_async(image)
                data = base64.b64encode(image_request.content)

            else:
                raise InvalidArgumentError("Cannot upload avatar. Invalid image.")

        mime, _ = mimetypes.guess_type(image)
        image_url = f"data:{mime};base64,{data.decode('utf-8')}"

        request = await self.__requester.request_async(
            url="https://character.ai/api/trpc/user.uploadAvatar?batch=1",
            options={
                "method": "POST",
                "headers": self.__client.get_headers(
                    token=kwargs.get("token", None),
                    web_next_auth=kwargs.get("web_next_auth", None),
                    include_web_next_auth=True,
                ),
                "body": json.dumps({"0": {"json": {"imageDataUrl": image_url}}}),
            },
        )

        if request.status_code == 200:
            response = request.json()[0]

            file_name = ((response.get("result", {})).get("data", {})).get("json", None)
            if file_name is not None:
                avatar = Avatar({"file_name": file_name})

                if check_image:
                    image_request = await self.__requester.request_async(avatar.get_url())

                    if image_request.status_code != 200:
                        raise UploadError(f"Cannot upload avatar. {image_request.text}")

                return avatar

        raise UploadError(
            "Cannot upload avatar. Maybe your web_next_auth token is invalid, "
            "or your image is too large, or your image didn't pass the filter."
        )
