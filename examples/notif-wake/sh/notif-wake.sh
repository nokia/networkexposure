#!/usr/bin/env bash

# Copyright 2021, 2022 Nokia
# Licensed under the BSD 3-Clause Clear License.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Get notification when device is available for data transmission.

# Install standard Unix tools, curl and nc (netcat) to use.

set -e

function print_help() {
    echo Usage: $0 '-m MSISDN -n NEF_URL -t TOKEN_URL -c CLIENT_ID -s CLIENT_SECRET -a AF_ID -N NOTIFY_URL'
    exit
}

while getopts m:n:t:c:s:a:N:h opts; do
   case ${opts} in
      m) MSISDN=$OPTARG ;;
      n) NEF=$OPTARG ;;
      t) TOKENURL=$OPTARG ;;
      c) CLIENTID=$OPTARG ;;
      s) CLIENTSECRET=$OPTARG ;;
      a) AF=$OPTARG ;;
      N) NOTIFYURL=$OPTARG ;;
      h) print_help ;;
      ?) print_help ;;
   esac
done

if [ -z "$MSISDN" ] || [ -z "$NEF" ] || [ -z "$TOKENURL" ] || [ -z "$CLIENTID" ] || [ -z "$CLIENTSECRET" ] || [ -z "$AF" ] || [ -z "$NOTIFYURL" ]; then print_help; fi

# Get access token
TOKEN=`curl -s $TOKENURL --data-urlencode 'grant_type=client_credentials' --data-urlencode "client_id=$CLIENTID" --data-urlencode "client_secret=$CLIENTSECRET" | jq -r .access_token`

if [ -z "$TOKEN" ]; then
    echo Error: Failed to get access token.
    false
fi

# Subscribe
RESOURCE=$(curl -i $NEF/3gpp-monitoring-event/v1/$AF/subscriptions \
    -H "Authorization: Bearer $TOKEN" \
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
curl $RESOURCE --fail -sSf -H "Authorization: Bearer $TOKEN" | jq

# Receive notification
# Make sure NOTIFYURL is in line with this.
echo "HTTP/1.1 200 OK" | nc -l -p 8080

# Delete subscription
curl $RESOURCE -sSf -H "Authorization: Bearer $TOKEN" -X DELETE

# If you experimented a lot and want to get rid of all subscriptions, you may try this:
# curl -H "Authorization: Bearer $TOKEN" $NEF/3gpp-monitoring-event/v1/$AF/subscriptions | jq '.[].self' | xargs curl -H "Authorization: Bearer $TOKEN" -X DELETE
