setup:
  # Replace with the http location of your Codecov
  # https://docs.codecov.io/docs/configuration#section-codecov-url
  codecov_url: https://${APP_NAME}.${DOMAIN}
  # codecov_api_url: <codecov-url> # this defaults to <codecov-url> and is designed to work out of the box like this
  # api_allowed_hosts: [] # this defaults to <codecov-url> and is designed to work out of the box like this
  # Replace with your Codecov Enterprise License key. This is required for the containers to function.
  # https://docs.codecov.io/docs/configuration#section-enterprise-license
  enterprise_license: ${CODECOV_LICENSE}
  admins: # https://docs.codecov.com/docs/configuration#instance-wide-admins
    - service: github
      username: ${CODECOV_ADMIN_GITHUB_USERNAME}
  http:
    cookie_secret: ${KEY_HEX_32} # Replace it with a random string
    cookies_domain: ${APP_NAME}.${DOMAIN}
  timeseries:
    enabled: true
  guest_access: "off"
github:
  client_id: ${CODECOV_GITHUB_CLIENT_ID}
  client_secret: ${CODECOV_GITHUB_CLIENT_SECRET}
  webhook_secret: ${CODECOV_GITHUB_WEBHOOK_SECRET}
  integration:
    id: ${CODECOV_GITHUB_APP_ID}
    pem: /config/key.pem
services:
  redis_url: "redis://redis:6379"
  database_url: "postgres://${APP_NAME}:${DATABASE_PASSWORD}@postgres:5432/${APP_NAME}"
  timeseries_database_url: "postgres://${APP_NAME}:${DATABASE_PASSWORD}@timescale:5432/${APP_NAME}"
  minio:
    host: ${S3_HOST}
    bucket: ${CODECOV_S3_BUCKET}
    region: ${S3_REGION}
    verify_ssl: true
    port: 443
    access_key_id: ${S3_ACCESS_KEY_ID}
    secret_access_key: ${S3_SECRET_ACCESS_KEY}
