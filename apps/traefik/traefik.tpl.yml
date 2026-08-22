global:
  checkNewVersion: false
  sendAnonymousUsage: false
log:
  level: INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
accesslog: {}
# format: common # common, json, logfmt
# filePath: /var/log/traefik/access.log
api:
  dashboard: true
ping:
  entryPoint: traefik
entryPoints:
  http:
    address: ":80"
  https:
    address: ":443"
    forwardedHeaders:
      trustedIPs:
        - 172.16.0.0/12
        - 10.0.0.0/8
  traefik:
    address: ":8080"
providers:
  docker:
    # endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: traefik
    watch: true
certificatesResolvers:
  acmeHttpChallengeResolver:
    acme:
      email: ${APPS_ADMIN_MAIL}
      storage: acme.json
      httpChallenge:
        entryPoint: http
  acmeCloudflareDnsChallengeResolver:
    acme:
      email: ${APPS_ADMIN_MAIL}
      storage: acme.json
      dnsChallenge:
        provider: cloudflare
        delayBeforeCheck: 0
