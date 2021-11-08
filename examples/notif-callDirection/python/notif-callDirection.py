#!/usr/bin/env python3
import argparse
import requests
import threading
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import uvicorn

def parse_args():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument('--msisdn', action='store', type=str, required=True, help="MSISDN, i.e. phone number of the device")
	arg_parser.add_argument('--nef', action='store', type=str, required=True, help="URL of NEF")
	arg_parser.add_argument('--username', action='store', type=str, required=True, help="User name")
	arg_parser.add_argument('--password', action='store', type=str, required=True, help="Password")
	arg_parser.add_argument('--notifyurl', action='store', type=str, required=True, help="URL where you expect the notifications")
	return arg_parser.parse_args()


class Client:
	def __init__(self, args: argparse.Namespace):
		self.args = args
		self.client = requests.Session()
		self.client.auth = (args.username, args.password)

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
