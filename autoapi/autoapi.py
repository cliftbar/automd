import mimetypes

from http.client import responses
from typing import Dict, Union, List, Callable, Type
from marshmallow import Schema
from webargs import fields, dict2schema
from werkzeug.local import LocalProxy
from flask import url_for, Flask

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

from autoapi.responses import ResponseObjectInterface
from autoapi.responses.responses import response_object_type_map, ValueResponse


class AutoAPI:
    config_key: str = "AutoAPI"
    function_key = "autoapi_spec"

    def __init__(self,
                 title: str,
                 app_version: str = "1.0.0",
                 openapi_version: str = "3.0.0",
                 info: Dict = None,
                 default_tag: str = None):
        """

        :param title: Application title
        :param app_version: Application version
        :param openapi_version: OpenAPI spec version presented.
        :param info: Detailed information about the application.
        :param default_tag: Tag to apply to endpoints if not specified in their decorator.
               Falls back to application title.
        """
        self.default_tag: Dict = {"name": default_tag or title}

        self.apispec_options: Dict = {
            "title": title,
            "app_version": app_version,
            "openapi_version": openapi_version,
            "info": {} if info is None else info,
            "plugins": [MarshmallowPlugin()]
        }

    def start_spec(self) -> APISpec:
        """
        Returns a new APISpec object based off the parameters this class
        :return: new APISpec class
        """
        api_spec: APISpec = APISpec(self.apispec_options["title"],
                                    self.apispec_options["app_version"],
                                    self.apispec_options["openapi_version"],
                                    info=self.apispec_options["info"],
                                    plugins=self.apispec_options["plugins"])

        return api_spec

    def register_path(self,
                      api_spec: APISpec,
                      path_url: str,
                      http_verb: str,
                      response_code: int,
                      summary: str = None,
                      description: str = None,
                      parameter_object: Union[Dict, Schema] = None,
                      response_object: Union[Type, ResponseObjectInterface] = None,
                      tags: List[Dict] = None) -> APISpec:
        """
        Register a new path to the provided APISpec object (passed in APISpec object is mutated).
        :param api_spec: APISpec to register the path to
        :param path_url: url of the path
        :param http_verb:
        :param response_code:
        :param summary:
        :param description:
        :param parameter_object: HTTP Parameters of the path
        :param response_object: HTTP response information
        :param tags: Tags for categorizing the path.  Defaults to the AutoAPI App Title
        :return: The same APISpec object passed in, but now with a new path register
        """

        if hasattr(parameter_object, "fields"):
            parameter_dict: Dict[str, fields.Field] = parameter_object.fields
        else:
            parameter_dict: Dict[str, fields.Field] = parameter_object

        location_argmaps: Dict[str, Dict[str, fields.Field]] = {}
        for name, field in parameter_dict.items():
            location: str = field.metadata.get("location", "query")
            if location not in location_argmaps:
                location_argmaps[location] = {}

            location_argmaps[location][name] = field

        location_schemas: Dict[str, Dict[str, Schema]] = {}
        for loc, argmap in location_argmaps.items():
            if loc not in location_schemas:
                location_schemas[loc] = {}

            location_schemas[loc] = dict2schema(argmap)

        class ParameterSchema(Schema):
            class Meta:
                include = {
                    loc: fields.Nested(schema, location=loc)
                    for loc, schema
                    in location_schemas.items()
                }

        response_interface: ResponseObjectInterface
        if response_object in response_object_type_map.keys():
            response_interface = response_object_type_map[response_object]
        elif getattr(response_object, "_name", None) in response_object_type_map.keys():
            response_interface = response_object_type_map[response_object._name]
        else:
            response_interface = response_object

        response_schema: Schema = response_interface.to_schema()

        content_type: str
        try:
            content_type = response_interface.content_type()
        except AttributeError as ae:
            content_type = mimetypes.MimeTypes().types_map[1][".txt"]
            # content_type = magic.from_buffer(str(response_object), mime=True)

        operations: Dict = {
            http_verb.lower(): {
                "responses": {
                    str(response_code): {
                        "description": responses[response_code],
                        "content": {
                            content_type: {
                                "schema": response_schema
                            }
                        }
                    }
                },
                "parameters": [{"in": "query", "schema": ParameterSchema()}],
                "summary": summary,
                "description": description,
                "tags": tags or [self.default_tag]
            }
        }

        api_spec.path(
            path=path_url,
            operations=operations,
        )

        return api_spec

    def application_to_apispec(self, app: Union[Flask, LocalProxy]) -> APISpec:
        """
        Create a new APISpec of the provided application that has been initialized with AutoAPI
        :param app: Flask app initialized with AutoAPI
        :return:
        """
        autoapi_spec: APISpec = self.start_spec()

        name: str
        for name, view in app.view_functions.items():
            if not hasattr(view, "methods"):
                continue
            method: str
            for method in view.methods:
                key: str = url_for(view.view_class.endpoint)
                value_func: Callable = getattr(view.view_class, method.lower())

                if hasattr(value_func, AutoAPI.function_key):
                    autoapi_spec_parameters: Dict = getattr(value_func, AutoAPI.function_key)
                    response_schemas: Dict = autoapi_spec_parameters.get("response_schemas")
                    parameter_schema: Dict = autoapi_spec_parameters.get("parameter_schema")
                    summary: str = autoapi_spec_parameters.get("summary")
                    description: str = autoapi_spec_parameters.get("description")
                    tags: List[Dict] = autoapi_spec_parameters.get("tags")
                    self.register_path(autoapi_spec,
                                       key,
                                       method,
                                       200,
                                       summary,
                                       description,
                                       parameter_schema,
                                       response_schemas["200"],
                                       tags)
        return autoapi_spec
