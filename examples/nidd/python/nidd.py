#!/usr/bin/env python3

# Copyright 2021, 2022 Nokia
# Licensed under the BSD 3-Clause Clear License.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import argparse
import requests
import threading
import base64

from requests.sessions import Session
from fastapi import FastAPI
from pydantic import BaseModel, parse_obj_as
from typing import List, Union, Optional
from starlette.routing import NoMatchFound
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


# Lots of data structures. Simplified versions of OpenAPI defined ones.

class NiddConfiguration(BaseModel):
	self: Optional[str] = None
	msisdn: str
	status: Optional[str] = None
	notificationDestination: Optional[str] = None


class NiddDownlinkDataTransfer(BaseModel):
	msisdn: str
	deliveryStatus: Optional[str] = None
	data: Optional[str] = None


class NiddUplinkDataNotification(BaseModel):
	data: str
	msisdn: str


class NiddDownlinkDataDeliveryStatusNotification(BaseModel):
	niddDownlinkDataTransfer: str
	deliveryStatus: str


notifications = Union[
	NiddUplinkDataNotification,
	NiddDownlinkDataDeliveryStatusNotification
]


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

	def get_config_url(self, msisdn: str)->str:
		print("Querying all resources")
		response = self.client.get(self.args.nef + '/3gpp-nidd/v1/'+self.args.af+'/configurations')
		response.raise_for_status()
		cfgs = parse_obj_as(List[NiddConfiguration], response.json())
		for cfg in cfgs:
			if cfg.msisdn == msisdn:
				return cfg.self
		raise NoMatchFound

	def configure_device(self, msisdn: str)->str:
		data = NiddConfiguration(msisdn=msisdn, notificationDestination=self.args.notifyurl+'/nidd-notif/'+msisdn)
		url = self.args.nef + '/3gpp-nidd/v1/'+self.args.af+'/configurations'
		response = self.client.post(url, json=data.dict(exclude_unset=True))
		if response.status_code >= 400:
			print("Device may have already been configured:", url, response.status_code)
			resource = self.get_config_url(self.args.msisdn)
		else:
			resource = response.headers['Location']
			print("Created:", response.json())
		print("Resource URL:", resource)
		return resource

	def deliver(self, msisdn: str, resource: str, data: bytes):
		req = NiddDownlinkDataTransfer(msisdn=msisdn, data=base64.b64encode(data))
		response = self.client.post(url=resource+'/downlink-data-deliveries', json=req.dict(exclude_unset=True))
		response.raise_for_status()
		print("Downlink result:", response.json())

	def deliver_str(self, msisdn: str, resource: str, string: str):
		self.deliver(msisdn, resource, string.encode('ascii'))


args = parse_args()
client = Client(args)

app = FastAPI()

def start_server()->threading.Thread:
	server = threading.Thread(target=uvicorn.run, args=(app,))
	server.start()
	return server

@app.post("/nidd-notif/{msisdn}")
def notification(msisdn: str, notif: notifications):
	print("Notification for", msisdn)
	if isinstance(notif, NiddUplinkDataNotification):
		string = base64.b64decode(notif.data).decode('ascii')
		print("Received", string)
	elif isinstance(notif, NiddDownlinkDataDeliveryStatusNotification):
		print("Downlink status", notif.deliveryStatus)

if __name__ == "__main__":
	start_server()
	resource = client.configure_device(args.msisdn)
	client.deliver_str(msisdn=args.msisdn, resource=resource, string="Hello, World!")
