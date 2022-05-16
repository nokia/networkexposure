#!/usr/bin/env python3

# Copyright 2021, 2022 Nokia
# Licensed under the BSD 3-Clause Clear License.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Run:
# pip install -r requirements.txt
# ./notif-wake.py

import argparse
import requests
import threading
import urllib

from requests.sessions import Session
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

def parse_args():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('-m', '--msisdn', action='store', type=str, required=True, help="MSISDN, i.e. phone number of the device")
	arg_parser.add_argument('-n', '--nef', action='store', type=str, required=True, help="URL of NEF")
	arg_parser.add_argument('-t', '--tokenurl', action='store', type=str, required=True, help="URL of authorization server serving access token")
	arg_parser.add_argument('-c', '--clientid', action='store', type=str, required=True, help="Client ID")
	arg_parser.add_argument('-s', '--clientsecret', action='store', type=str, required=True, help="Client secret")
	arg_parser.add_argument('-a', '--af', action='store', type=str, required=True, help="Application Function ID")
	arg_parser.add_argument('-N', '--notifyurl', action='store', type=str, required=True, help="URL where you expect the notifications")
	return arg_parser.parse_args()

class Client:
	def __init__(self, args: argparse.Namespace):
		self.args = args
		self.client = requests.Session()
		self.client.headers["Authorization"] = "Bearer " + self._get_token()

	def _get_token(self) -> str:
		data={"grant_type": "client_credentials", "client_id": self.args.clientid, "client_secret": self.args.clientsecret}
		resp = requests.post(url=self.args.tokenurl, data=data)
		access_token = resp.json()["access_token"]
		return access_token

	def subscribe(self)->str:
		data = {"msisdn": self.args.msisdn, "notificationDestination": self.args.notifyurl, "monitoringType": "UE_REACHABILITY", "reachabilityType": "DATA", "maximumNumberOfReports": 1}
		response = self.client.post(self.args.nef + '/3gpp-monitoring-event/v1/'+self.args.af+'/subscriptions', json=data)
		response.raise_for_status()
		resource = response.headers['Location']
		print("Created:", response.json())
		print("Resource URL:", resource)
		return resource

	def query(self, resource: str):
		response = self.client.get(resource)
		print("Queried:", response.json())

	def delete(self, resource: str):
		self.client.delete(resource)


class MonitoringNotification(BaseModel):
	subscription: str


args = parse_args()
client = Client(args)

app = FastAPI()

def start_server()->threading.Thread:
	server = threading.Thread(target=uvicorn.run, args=(app,))
	server.start()
	return server

@app.post("/")
def notification(notif: MonitoringNotification):
	print("Notification for:", notif.subscription)
	client.delete(notif.subscription)

if __name__ == "__main__":
	start_server()
	resource = client.subscribe()
	client.query(resource)
