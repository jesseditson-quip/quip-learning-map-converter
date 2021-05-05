#!/usr/bin/python

import json
import os
import re
import sys
import yaml
from six.moves import urllib
from html.parser import HTMLParser

"""
This script takes the html output of a Quip doc, and outputs a yaml file in
the format of a learning map.
"""

# pass the doc ID as the first argument to the script
doc_id = sys.argv[1]
assert doc_id, "Pass a document ID as the first argument to this script."


# an error message to show the user if they're not logged in via quip-cli
login_error = "You don't seem to be logged in. Set QUIP_TOKEN to an access token or try installing quip-cli and running quip-cli login."

class QuipHTMLToYamlParser(HTMLParser):
    """
    This class handles parsing html to yaml. The output format (as a dict) is:

    {
        # Main title and description for the page
        ### comes from the title of the doc
        "title": "",
        ### comes from the first paragraph of the doc
        "description": "",
        # Each step is an array element in the "step" array...
        ### Each h2 at the root of the doc defines a new step
        "steps": [
            # step 1
            {
                # Basic info for the step
                ### The content of the h2
                "navtitle": "",
                ### The first blockquote below the h2, or the h2 if there is none.
                "title": "",
                ### The first paragraph below the h2/h3
                "description": "",
                # Each column of each step is an array element in the "column" array...
                ### Each h3 defines a new column
                "columns": [
                    # column 1 in step 1
                    {
                        # Basic info for the column
                        ### The content of the h3
                        "title": "",
                        # Each item (in each column, in each step) is an array element in the "items" array...
                        ### Each h3 should be followed by a number of lists. Each list is an item.
                        ### The bullets in each list should start with a key name and a colon, then the content for that key.
                        ### For instance: "title: my title"
                        "items": [
                            # item 1 in step 1 in column 1
                            {
                                # item info
                                "title": "",
                                "icon": "",
                                "url": ""
                            }
                        ]
                    }
                ]
            }
        ]
    }
    """

    item_regex = re.compile("(\w+):(.+)")

    def __init__(self):
        HTMLParser.__init__(self)
        # this holds our output as we build it up
        self.output = {
            "title": "",
            "description": "",
            "steps": []
        }
        self.current_tags = []
        self.state = "title"
    
    def handle_starttag(self, tag, attrs):
        self.current_tags.append(tag)
        
        if tag == "ul" and (self.state == "column" or self.state == "item"):
            self.state = "item"
            if not self.current_column.get("items", None):
                self.current_column["items"] = []
            self.current_item = {}
            self.current_column["items"].append(self.current_item)

    def handle_endtag(self, tag):
        self.current_tags.pop()

    def handle_data(self, raw):
        data = raw.encode("utf-8")
        if len(self.current_tags) == 0:
            return
        current_tag = self.current_tags[-1]
        if current_tag == "h1" and self.state == "title":
            self.defining_steps = False
            self.output["title"] = data
        if current_tag == "p" and self.state == "title":
            self.output["description"] += data + "\n"
        if current_tag == "h2":
            self.state = "step"
            self.current_step = {
                "navtitle": data,
                "title": data
            }
            self.output["steps"].append(self.current_step)
        if current_tag == "blockquote" and self.state == "step":
            self.current_step["title"] = data
        if current_tag == "p" and self.state == "step":
            if not self.current_step.get("description", None):
                self.current_step["description"] = ""
            self.current_step["description"] += data + "\n"
        if current_tag == "h3" and self.state == "step":
            self.state = "column"
            if not self.current_step.get("columns", None):
                self.current_step["columns"] = []
            self.current_column = {
                "title": data
            }
            self.current_step["columns"].append(self.current_column)
        if current_tag == "span" and self.state == "item":
            match = QuipHTMLToYamlParser.item_regex.match(data)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                self.current_key = key
                self.current_item[key] = value
        elif "span" in self.current_tags:
            self.current_item[self.current_key] += data


def fetch_doc(threadId):
    url = "https://platform.quip.com/1/threads/%s" % threadId
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": "Bearer %s" % get_token()
    }
    req = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())
    return data

def get_token():
    token = os.environ.get("QUIP_TOKEN", None)
    if token:
        return token
    # open the .quiprc file that is written by qla login,
    # since that will probably have a valid token in it
    data = {}
    with open(os.path.join(os.path.expanduser("~"), ".quiprc"), "r") as f:
        data = json.loads(f.read())
    # read either the config for quip.com or the first config available.
    config = data["sites"].get("quip.com", None)
    if not config:
        first_site = next(iter(data["sites"]))
        if first_site:
            config = data["sites"][first_site]
    # make sure we have a token, and if not tell the user to try logging in.
    if not config:
        assert first_site is not None, login_error
    # just use the token from the first site we find.
    return str(config["accessToken"])

def parse_document(doc):
    parser = QuipHTMLToYamlParser()
    parser.feed(doc["html"])
    return yaml.dump(parser.output, default_flow_style=False)

def main():
    doc_data = fetch_doc(doc_id)
    yaml = parse_document(doc_data)
    print(yaml)

if __name__ == "__main__":
    main()
