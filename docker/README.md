# vrc-embed docker scripts

This folder contains the necessary Dockerfiles and an example docker-compose setup for running vrc-embed in Docker.

Note that this setup does not include a reverse-proxy. vrc-embed is a standard Quart/hypercorn application, so any instructions for proxying them apply here as well.

## Using docker-compose

- Copy `docker-compose.yml.sample` into **the root of vrc-embed's source code**:
  ```
  $ cd /path/to/vrc-embed
  $ cp docker/docker-compose.yml.sample docker-compose.yml
  ```
- Modify the file as explained in the comments.
- Copy the example config (`config.toml.docker`) into the root of vrc-embed's source code:
  ```
  $ cp docker/config.toml.docker config.toml
  ```
- Set the configuration options as needed.
- Run with regular docker compose options: `docker compose up` to start, `docker compose down` to stop.

To update the container:

- `git pull` the latest version of vrc-embed.
- Pass the `--build` flag to `docker compose up` and let it rebuild the containers.
