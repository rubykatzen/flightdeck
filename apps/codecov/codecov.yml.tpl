setup:
  # Replace with the http location of your Codecov
  # https://docs.codecov.io/docs/configuration#section-codecov-url
  codecov_url: https://${APP_NAME}.${DOMAIN}
  # codecov_api_url: <codecov-url> # this defaults to <codecov-url> and is designed to work out of the box like this
  # api_allowed_hosts: [] # this defaults to <codecov-url> and is designed to work out of the box like this
  # Replace with your Codecov Enterprise License key. This is required for the containers to function.
  # https://docs.codecov.io/docs/configuration#section-enterprise-license
  enterprise_license: ${LICENSE}
  admins: # https://docs.codecov.com/docs/configuration#instance-wide-admins
    - service: github
      username: ${ADMIN_GITHUB_USERNAME}
  http:
    cookie_secret: ${SESSION_KEY} # Replace it with a random string
    cookies_domain: ${APP_NAME}.${DOMAIN}
  timeseries:
    enabled: true
  guest_access: "off"
github:
  client_id: ${GITHUB_CLIENT_ID}
  client_secret: ${GITHUB_CLIENT_SECRET}
  webhook_secret: ${GITHUB_WEBHOOK_SECRET}
  integration:
    id: ${GITHUB_APP_ID}
    pem: /config/key.pem
services:
  redis_url: "redis://redis:6379"
  database_url: "postgres://${APP_NAME}:${DATABASE_PASSWORD}@postgres:5432/${APP_NAME}"
  timeseries_database_url: "postgres://${APP_NAME}:${DATABASE_PASSWORD}@timescale:5432/${APP_NAME}"
  minio:
    host: ${S3_HOST}
    bucket: ${S3_BUCKET}
    region: ${S3_REGION}
    verify_ssl: true
    port: 443
    access_key_id: ${S3_ACCESS_KEY_ID}
    secret_access_key: ${S3_SECRET_ACCESS_KEY}
