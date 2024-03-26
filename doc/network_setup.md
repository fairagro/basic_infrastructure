# Nextcloud Network Setup #

The network setup for Nextcloud is complex. There is one main issue that needs to dealt with. It results from the fact that we're hosting nextcloud on-premise:

We want to offer nextcloud publicly on the Internet, so we need to assign it a public IP. But this public IP is not reachable from within the ZALF network.

This is a typical issue that arises if you setup a private network that is connected to the Internet by a network router that performs NATting. There are two solutions to deal with this on the network level:

* Setup NAT Reflection (also called NAT Hairpinning or NAT Loopback). This is generaly considered to be an ugly solution, so best practice is to pursue the second option:
* Operate an internal DNS server. Whenever you would like to make a service internally available that is hosted on one of your public IPs, you create an additional internal DNS entry that maps the service URL to the internal IP of the service.

The originial networking approach for nextcloud is based on second solution. Unfortunately ZALF IT (who controls the internal DNS servers) is not willing to support it, so we were forced to find a workaround solution. The following two sections will depict the intended/planned solution as well as the workaround solution.

## The intended Nextcloud Network Setup ##

The basic idea is: we need two IP addresses for the kubernetes cluster: the first/internal IP is reachable from within the ZALF network while the second/"external" IP is hosted within a DMZ (demilitarized zone) and NATted to an actual external IP. Both IPs are shared by all web services hosted within the kubernetes cluster, so they are also used by nextcloud and collabora office.

On the kuberentes cluster level these IPs are assigned to MetalLB that perform fail-over clustering on them. I.e. these IPs are assigned to one of the kubernetes cluster nodes. In case this nodes fails, the IPs are automatically transferred to another cluster node. Both IPs are then bound to kubernetes ingress classes. We use ingress-nginx for this purpose.

An kubernetes ingress class is in fact a reverse proxy (based on nginx in our case). Now every service in cluster can subscribe to one or both ingress classes (by creating the correspong ingress objects) and register its own hostnames/fqdns that in turn gets forwarded to this service. This dispatch is done on OSI network layer 7 -- so it only works for HTTP/HTTPS requests. The distinguishing marker for the dispatch is host header field of the incoming HTTP request.

Now we use an external DNS service (cloudflare in our case) to create external DNS entries that map to the external IP address of our service. In order to be able to access the service also from with the ZALF network, we would like to have additional internal DNS entries created, that map to the internal IP.

## The workaround Nextcloud Network Setup ##

As ZALF IT denies internal DNS entries for our setup, we've introduced an additional external reverse proxy that runs in the cloud. The public IP of this reverse proxy is accessible from the ZALF network because the IP is not hosted by ZALF and thus not affected by the NATting issue explained earlier.

External DNS entries now have to point to the external reverse proxy.

There are several options to setup the reverse proxy:

* Terminate the TLS session and establish a new TLS connection to ZALF.
* TLS-passthrough: do not terminate the TLS session but forward it to ZALF.

The first solution is quite complex: it requires two DNS entries as well as two certificates per service -- one for the ZALF endpoint and one for the external reverse proxy endpoint. Also the reverse proxy configuration itself is complex.

So we've opted for the second solution, using an nginx reverse proxy. There are two configuration files needed.

* `/etc/nginx/modules-enabled/80-fairagro-reverse proxy.conf`:
  
    ```plaintext
    stream {
        map $ssl_preread_server_name $name {
            nextcloud-test.fairagro.net 193.175.153.124:443;
            collabora-test.fairagro.net 193.175.153.124:443;
        }

        server {
            listen      443;
            proxy_pass  $name;
            ssl_preread on;
            resolver    1.1.1.1;
        }
    }
    ```

    Note that each hostname needs to be listed in the map section. The following IP address is the external ingress-nginx IP address of the kubernetes cluster.
* `/etc/nginx/sites-enabled/http_to_https`:

    ```plaintext
    server {
        listen 80 default_server;
        error_page 497 =301 https://$host$request_uri;
    }
    ```

    This is a simple HTTP->HTTPS redirection for all hostnames.

## Additional Collabora Office considerations ##

The use Collabora Office for office document collaboration. The communication between Nextcloud and Collabora office is done by the so-called WOPI protocol. With this protocol there are the following communication channels:

* `Nextcloud -> Collabora Office`: Nextcloud checks if Collabora Office is available.
* `Collabora Office -> Nextcloud`: Collabora Office requests documents from Nextcloud.
* `Browser -> Nextcloud`: this is the obvious communication between the browser of the Nextcloud user and the Nextcloud server.
* `Browser -> Collabora Office`: when the user requests to edit a document with Collabora Office, Nextcloud will answer with an HTTP redirect to Collabora Office.

In Nextcloud you will need to tell the Collabora Office integration app (called 'richdocuments') the FQDN of Collabora Office. This FQDN will be used for the `Nextcloud -> Collabora Office` communication as well as the `Browser -> Collabora Office` communication. The the same FDQN needs to be resolvable to a working Collabora Office IP -- within ZALF as well as outside of ZALF. This is true work external reverse proxy solution as well as for the intended internal DNS entry solution.