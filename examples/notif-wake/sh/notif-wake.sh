#!/usr/bin/env bash

# Copyright 2021 Nokia
# Licensed under the BSD 3-Clause Clear License.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Get notification when device is available for data transmission.

# Install standard Unix tools, curl and nc (netcat) to use.

set -e

function print_help() {
    echo Usage: $0 '-n NEF_URL -u USERNAME -p PASSWORD -a AF_ID -N NOTIFY_URL'
}

while getopts m:n:u:p:a:N:h opts; do
   case ${opts} in
      m) MSISDN=$OPTARG ;;
      n) NEF=$OPTARG ;;
      u) USERNAME=$OPTARG ;;
      p) PASSWORD=$OPTARG ;;
      a) AF=$OPTARG ;;
      N) NOTIFYURL=$OPTARG ;;
      h) print_help ;;
      ?) print_help ;;
   esac
done

if [ -z "$NEF" ] || [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$AF" ] || [ -z "$NOTIFYURL" ]; then print_help; fi

# Subscribe
RESOURCE=$(curl $NEF/3gpp-monitoring-event/v1/$AF/subscriptions \
    --user $USERNAME:$PASSWORD \
    -i -sSf -b cookies.txt -c cookies.txt \
    -H 'Content-Type: application/json' \
    -d '{"msisdn": "'$MSISDN'", "notificationDestination": "'$NOTIFYURL'", "monitoringType": "UE_REACHABILITY", "reachabilityType": "DATA", "maximumNumberOfReports": 1}' \
    | grep -Ei '^Location:' | sed -r 's/^Location: *//i' | tr -d '\r\n')

if [ -z "$RESOURCE" ]; then
    echo Error: Subscription failed.
    false
fi

echo Resource URL: $RESOURCE

# Query subscription
echo Queried:
curl $RESOURCE --fail -sSf --user $USERNAME:$PASSWORD -b cookies.txt -c cookies.txt | jq

# Receive notification
# Make sure NOTIFYURL is in line with this.
echo "HTTP/1.1 200 OK" | nc -l -p 8080

# Delete subscription
curl $RESOURCE -sSf --user $USERNAME:$PASSWORD -b cookies.txt -c cookies.txt -X DELETE

# If you experimented a lot and want to get rid of all subscriptions, you may try this:
# curl --user $USERNAME:$PASSWORD -c cookies.txt -b cookies.txt $NEF/3gpp-monitoring-event/v1/$AF/subscriptions | jq '.[].self' | xargs curl --user $USERNAME:$PASSWORD -b cookies.txt -X DELETE
