// Copyright 2021, 2022 Nokia
// Licensed under the BSD 3-Clause Clear License.
// SPDX-License-Identifier: BSD-3-Clause-Clear

// Run:
// go run ./...

package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"sync"
	"time"

	"github.com/nokia/restful"
)

var (
	msisdn       = flag.String("msisdn", "", "MSISDN, i.e. phone number of the device")
	nef          = flag.String("nef", "", "URL of NEF")
	tokenURL     = flag.String("tokenurl", "", "URL of authorization server serving access token")
	clientID     = flag.String("clientid", "", "Client ID")
	clientSecret = flag.String("clientsecret", "", "Client Secret")
	af           = flag.String("af", "", "Application Function ID")
	notifyURL    = flag.String("notifyurl", "", "URL where you expect the notifications")
)

type MonitoringEventSubscription struct { // Simplified
	Self                    string `json:"self,omitempty"`
	Msisdn                  string `json:"msisdn,omitempty"`
	NotificationDestination string `json:"notificationDestination"`
	MonitoringType          string `json:"monitoringType"`
	MaximumNumberOfReports  uint32 `json:"maximumNumberOfReports,omitempty"`
	ReachabilityType        string `json:"reachabilityType,omitempty"`
}

type MonitoringNotification struct {
	Subscription string `json:"subscription"`
}

func checkFlags() {
	flag.Parse()
	flag.VisitAll(func(f *flag.Flag) {
		if f.Value.String() == "" {
			println("Argument not set: -" + f.Name)
			flag.Usage()
			os.Exit(1)
		}
	})
}

func panicIf(err error) {
	if err != nil {
		panic(err)
	}
}

// Server

type server struct {
	client *restful.Client
	wg     *sync.WaitGroup
}

func (s *server) notify(ctx context.Context, data *MonitoringNotification) error {
	if data.Subscription == "" {
		return restful.NewError(nil, http.StatusBadRequest, "missing subscription")
	}
	defer s.wg.Done()
	fmt.Println("Notification:", data.Subscription)
	panicIf(s.client.Delete(ctx, data.Subscription))
	return nil
}

func startServer(client *restful.Client, wg *sync.WaitGroup) {
	s := server{client: client, wg: wg}
	s.wg.Add(1)
	r := restful.NewRouter()
	r.HandleFunc("/", s.notify)
	go r.ListenAndServe(":8080")
}

// Client

func createClient(root string) *restful.Client {
	return restful.NewClient().
		Root(root).
		Retry(3, 500*time.Millisecond, 2*time.Second).
		Timeout(10 * time.Second)
}

// Get access token

type tokenResp struct {
	AccessToken string `json:"access_token"`
}

func getAccessToken() (string, error) {
	c := createClient("")

	req := url.Values{}
	req.Set("grant_type", "client_credentials")
	req.Set("client_id", *clientID)
	req.Set("client_secret", *clientSecret)
	var resp tokenResp

	_, err := c.PostForm(context.Background(), *tokenURL, req, &resp)
	return resp.AccessToken, err
}

func subscribe(client *restful.Client, token string) string {
	ctx := context.Background()

	data := MonitoringEventSubscription{Msisdn: *msisdn, NotificationDestination: *notifyURL, MonitoringType: "UE_REACHABILITY", MaximumNumberOfReports: 1, ReachabilityType: "DATA"}
	var created MonitoringEventSubscription
	headers := http.Header{}
	headers.Set("Authorization", "Bearer "+token)
	resp, err := client.SendRecv2xx(ctx, http.MethodPost, "/3gpp-monitoring-event/v1/"+*af+"/subscriptions", headers, &data, &created)
	panicIf(err)
	resource, err := resp.Location()
	fmt.Printf("Created: %+v\n", created)
	fmt.Printf("Resource URL: %v\n", resource)
	return resource.String()
}

func query(client *restful.Client, resource, token string) {
	ctx := context.Background()

	var created MonitoringEventSubscription
	headers := http.Header{}
	headers.Set("Authorization", "Bearer "+token)
	_, err := client.SendRecv2xx(ctx, http.MethodGet, resource, headers, nil, &created)
	panicIf(err)
	fmt.Printf("Queried: %+v\n", created)
}

// Main

func main() {
	checkFlags()

	token, err := getAccessToken()
	panicIf(err)

	var wg sync.WaitGroup
	client := createClient(*nef)
	startServer(client, &wg)
	resource := subscribe(client, token)
	query(client, resource, token)
	wg.Wait()
}
