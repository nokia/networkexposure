// Copyright 2021 Nokia
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
	"net/http/cookiejar"
	"os"
	"sync"

	"github.com/nokia/restful"
)

var (
	msisdn    = flag.String("msisdn", "", "MSISDN, i.e. phone number of the device")
	nef       = flag.String("nef", "", "URL of NEF")
	username  = flag.String("username", "", "User name")
	password  = flag.String("password", "", "Password")
	af        = flag.String("af", "", "Application Function ID")
	notifyURL = flag.String("notifyurl", "", "URL where you expect the notifications")
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

func createClient() *restful.Client {
	jar, _ := cookiejar.New(nil)
	return restful.NewClient().
		Root(*nef).
		SetBasicAuth(*username, *password).
		SetJar(jar)
}

func subscribe(client *restful.Client) {
	ctx := context.Background()

	data := MonitoringEventSubscription{Msisdn: *msisdn, NotificationDestination: *notifyURL, MonitoringType: "UE_REACHABILITY", MaximumNumberOfReports: 1, ReachabilityType: "DATA"}
	var created MonitoringEventSubscription
	resource, err := client.Post(ctx, "/3gpp-monitoring-event/v1/"+*af+"/subscriptions", &data, &created)
	panicIf(err)
	fmt.Printf("Created: %+v\n", created)
	fmt.Printf("Resource URL: %v\n", resource)

	panicIf(client.Get(ctx, resource.String(), &data))
	fmt.Printf("Queried: %+v\n", data)
}

// Main

func main() {
	checkFlags()
	var wg sync.WaitGroup
	client := createClient()
	startServer(client, &wg)
	subscribe(client)
	wg.Wait()
}
