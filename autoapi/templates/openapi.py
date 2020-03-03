#!/usr/bin/python
#
#  Copyright 2017 Otto Seiskari
#  Licensed under the Apache License, Version 2.0.
#  See http://www.apache.org/licenses/LICENSE-2.0 for the full text.
#
#  This file is based on
#  https://github.com/swagger-api/swagger-ui/blob/4f1772f6544699bc748299bd65f7ae2112777abc/dist/index.html
#  (Copyright 2017 SmartBear Software, Licensed under Apache 2.0)
#
"""
Usage:
    python swagger-yaml-to-html.py < /path/to/api.yaml > doc.html
"""
from typing import Dict, List, Any, Union, Hashable

import yaml, json, sys

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Swagger UI</title>
  <link href="https://fonts.googleapis.com/css?family=Open+Sans:400,700|Source+Code+Pro:300,600|Titillium+Web:400,600,700" rel="stylesheet">
  <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.2.2/swagger-ui.css" >
  <style>
    html
    {
      box-sizing: border-box;
      overflow: -moz-scrollbars-vertical;
      overflow-y: scroll;
    }
    *,
    *:before,
    *:after
    {
      box-sizing: inherit;
    }
    body {
      margin:0;
      background: #fafafa;
    }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.2.2/swagger-ui-bundle.js"> </script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/3.2.2/swagger-ui-standalone-preset.js"> </script>
<script>
window.onload = function() {
  var spec = %s;
  // Build a system
  const ui = SwaggerUIBundle({
    spec: spec,
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "StandaloneLayout"
  })
  window.ui = ui
}
</script>
</body>
</html>
"""


def generate_template_from_yaml(spec_yaml: str) -> str:
    spec: Dict = yaml.load(spec_yaml, Loader=yaml.FullLoader)
    return generate_template_from_dict(spec)


def generate_template_from_dict(spec_dict: Dict) -> str:
    return TEMPLATE % json.dumps(spec_dict)


def main():
    spec_yaml = sys.stdin.read()
    html_template = generate_template_from_yaml(spec_yaml)
    print(html_template)


if __name__ == "__main__":
    main()