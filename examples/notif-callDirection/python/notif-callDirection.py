#!/usr/bin/env python3

# Copyright 2021, 2022 Nokia
# Licensed under the BSD 3-Clause Clear License.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import argparse
import requests
import threading
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import uvicorn

def parse_args():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('-m', '--msisdn', action='store', type=str, required=True, help="MSISDN, i.e. phone number of the device")
	arg_parser.add_argument('-n', '--nef', action='store', type=str, required=True, help="URL of NEF")
	arg_parser.add_argument('-t', '--tokenurl', action='store', type=str, required=True, help="URL of authorization server serving access token")
	arg_parser.add_argument('-c', '--clientid', action='store', type=str, required=True, help="Client ID")
	arg_parser.add_argument('-s', '--clientsecret', action='store', type=str, required=True, help="Client secret")
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
		# Criteria tells which events to subscribe to: "Busy", "NotReachable", "NoAnswer", "Disconnected" (call ended) or "CalledNumber" (call attempt).
		# Criteria "Answer" is available at call event notification, but not at call direction, because at that moment one cannot redirect the call.
		data = {"callDirectionSubscription": {"callbackReference" : {"notifyURL": self.args.notifyurl, "notificationFormat" : "JSON"}, "filter" : {"address" : [self.args.msisdn], "criteria" : ["CalledNumber"], "addressDirection" : "Called"}, "clientCorrelator" : "1234"}}
		response = self.client.post(self.args.nef + '/ParlayREST/callnotification/v1/subscriptions/callDirection', json=data)
		response.raise_for_status()
		resource = response.headers['Location']
		print("Created:", response.json())
		print("Resource URL:", resource)
		return resource

	def query(self, resource):
		response = self.client.get(resource)
		print("Queried:", response.json())

class EventDescription(BaseModel):
	callEvent: str


class CallEventNotification(BaseModel):
	calledParticipant: str
	callingParticipant: str
	eventDescription: EventDescription
	notificationType: str


class CallEventNotificationRequest(BaseModel):
	callEventNotification: CallEventNotification


class Action(BaseModel):
	actionToPerform: str
	routingAddress: Optional[str]


class ActionResponse(BaseModel):
	action: Action


args = parse_args()
client = Client(args)

app = FastAPI()

def start_server()->threading.Thread:
	server = threading.Thread(target=uvicorn.run, args=(app,))
	server.start()
	return server

@app.post("/", response_model=ActionResponse, response_model_exclude_none=True)
def callDirectionNotification(notif: CallEventNotificationRequest):
	print("Called:", notif.callEventNotification.calledParticipant)
	print("Caller:", notif.callEventNotification.callingParticipant)
	print("Event:", notif.callEventNotification.eventDescription.callEvent)

	# Possible actions: "Route" (to another number), "Continue", "EndCall" or "Deferred" (wait till a decision is made, e.g. voice CAPTCHA is done)
	rogueCallers = ['tel:1234567890', 'sip:rogue@example.com']
	if notif.callEventNotification.callingParticipant in rogueCallers:
		resp = ActionResponse(action={'actionToPerform': 'EndCall'})
	else:
		resp = ActionResponse(action={'actionToPerform': 'Continue'})
	return resp


if __name__ == "__main__":
	server = start_server()
	resource = client.subscribe()
	client.query(resource)
