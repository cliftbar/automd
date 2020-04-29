import inspect
import mimetypes

from http.client import responses
from inspect import Signature
from typing import Dict, Union, List, Callable, Type, Tuple
from marshmallow import Schema
from webargs import fields
from werkzeug.local import LocalProxy
from flask import url_for, Flask

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

from automd.responses import ResponseObjectInterface
from automd.responses.responses import response_object_type_map, type_field_mapping


class AutoMD:
    config_key: str = "AutoMD"
    function_key = "automd_spec"

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

    def parse_parameter_schema(self,
                               parameter_object: Union[Dict, Schema],
                               func_signature: Signature,
                               path_url: str,
                               http_verb: str) -> Schema:
        if parameter_object is None:
            parameter_signature_dict = {}
            for name, param in func_signature.parameters.items():
                if name == "self":
                    continue
                # default_val = None if param.default == inspect._empty else param.default

                field_args: Dict = {
                    "required": (param.default == inspect._empty)
                }

                if param.default != inspect._empty:
                    field_args["doc_default"] = param.default

                if param.default is None:
                    field_args["allow_none"] = param.default

                if type_field_mapping[param.annotation] in [fields.Raw, fields.Field]:
                    field_args["description"] = "parameter of unspecified type"

                field = type_field_mapping[param.annotation](**field_args)
                parameter_signature_dict[name] = field
            parameter_object = parameter_signature_dict

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
            # TODO: Source a better Schema Name
            url_name: str = "".join([part.title() for part in path_url.split("/")])
            schema_name: str = f"{url_name}{http_verb.title()}{loc.title()}Schema"
            location_schemas[loc] = Schema.from_dict(argmap, name=schema_name)

        class ParameterSchema(Schema):
            class Meta:
                include = {
                    loc: fields.Nested(schema, location=loc, name=loc)
                    for loc, schema
                    in location_schemas.items()
                }

        return ParameterSchema()

    def parse_response_schema(self,
                              response_object: Union[Type, ResponseObjectInterface],
                              path_url: str,
                              http_verb: str) -> Tuple[Schema, str]:
        response_interface: ResponseObjectInterface
        if response_object in response_object_type_map.keys():
            response_interface = response_object_type_map[response_object]
        elif getattr(response_object, "_name", None) in response_object_type_map.keys():
            response_interface = response_object_type_map[response_object._name]
        else:
            response_interface = response_object

        response_schema: Schema
        if response_interface is not None:
            response_schema = response_interface.to_schema()
        else:
            url_name: str = "".join([part.title() for part in path_url.split("/")])
            response_schema = Schema.from_dict({}, name=f"{url_name}{http_verb.title()}ResponseSchema")

        content_type: str
        try:
            content_type = response_interface.content_type()
        except AttributeError as ae:
            content_type = mimetypes.MimeTypes().types_map[1][".txt"]
            # content_type = magic.from_buffer(str(response_object), mime=True)

        return response_schema, content_type

    def register_path(self,
                      api_spec: APISpec,
                      path_url: str,
                      http_verb: str,
                      response_code: int,
                      summary: str = None,
                      description: str = None,
                      parameter_object: Union[Dict, Schema] = None,
                      response_object: Union[Type, ResponseObjectInterface] = None,
                      func_signature: Signature = None,
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
        :param func_signature: inspection Signature object of the API call function
        :param tags: Tags for categorizing the path.  Defaults to the AutoMD App Title
        :return: The same APISpec object passed in, but now with a new path register
        """

        parameter_schema: Schema = self.parse_parameter_schema(parameter_object, func_signature, path_url, http_verb)

        response_schema, content_type = self.parse_response_schema(response_object, path_url, http_verb)

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
                "parameters": [{"in": "query", "name": "test", "schema": parameter_schema}],
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
        Create a new APISpec of the provided application that has been initialized with AutoMD
        :param app: Flask app initialized with AutoMD
        :return:
        """
        automd_spec: APISpec = self.start_spec()

        name: str
        for name, view in app.view_functions.items():
            if not hasattr(view, "methods"):
                continue
            method: str
            for method in view.methods:
                key: str = url_for(view.view_class.endpoint)
                value_func: Callable = getattr(view.view_class, method.lower())

                if hasattr(value_func, AutoMD.function_key):
                    automd_spec_parameters: Dict = getattr(value_func, AutoMD.function_key)
                    response_schemas: Dict = automd_spec_parameters.get("response_schemas")
                    parameter_schema: Dict = automd_spec_parameters.get("parameter_schema")
                    func_signature: Signature = automd_spec_parameters.get("func_signature")
                    summary: str = automd_spec_parameters.get("summary")
                    description: str = automd_spec_parameters.get("description")
                    tags: List[Dict] = automd_spec_parameters.get("tags")
                    self.register_path(automd_spec,
                                       key,
                                       method,
                                       200,
                                       summary,
                                       description,
                                       parameter_schema,
                                       response_schemas["200"],
                                       func_signature,
                                       tags)
        return automd_spec