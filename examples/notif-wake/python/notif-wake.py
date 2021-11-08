#!/usr/bin/env python3

# Copyright 2021 Nokia
# Licensed under the BSD 3-Clause Clear License.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import argparse
import requests
import threading

from requests.sessions import Session
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

def parse_args():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('--msisdn', action='store', type=str, required=True, help="MSISDN, i.e. phone number of the device")
	arg_parser.add_argument('--nef', action='store', type=str, required=True, help="URL of NEF")
	arg_parser.add_argument('--username', action='store', type=str, required=True, help="User name")
	arg_parser.add_argument('--password', action='store', type=str, required=True, help="Password")
	arg_parser.add_argument('--af', action='store', type=str, required=True, help="Application Function ID")
	arg_parser.add_argument('--notifyurl', action='store', type=str, required=True, help="URL where you expect the notifications")
	return arg_parser.parse_args()

class Client:
	def __init__(self, args: argparse.Namespace):
		self.args = args
		self.client = requests.Session()
		self.client.auth = (args.username, args.password)

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
