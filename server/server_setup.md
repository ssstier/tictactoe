## Server Setup Instructions for Tic-Tac-Toe Online

### Introduction:
The Tic-Tac-Toe Online server requires trusted SSL certificates for secure communication. This document provides instructions on setting up the server, obtaining trusted SSL certificates, and using them.

### Prerequisites:
- Ensure you have Docker installed on your machine.
- Familiarity with SSL/TLS for encrypted communications.

### Understanding the SSL Certificates:
The Tic-Tac-Toe Online server uses SSL for encrypted communications. Two primary files are essential for this:

1. **combined_cert.pem**: This file combines the server's certificate and any intermediate certificates. It's used for establishing and validating the secure connection.
   
2. **private_key.pem**: This is the private key corresponding to the server's certificate. It must be kept secret and secure.

Ensure that your `combined_cert.pem` is not expired. You can check the validity using:
openssl x509 -noout -dates -in combined_cert.pem


### Obtaining Trusted SSL Certificates:
For production use, you need to obtain an SSL certificate from a trusted Certificate Authority (CA). Many providers offer this service, including:

- Let's Encrypt
- Comodo
- DigiCert
- GlobalSign

Follow the CA's instructions to obtain a certificate. Once acquired, you will have the server certificate and potentially some intermediate certificates. Concatenate them into a single `combined_cert.pem` file, starting with the server certificate followed by the intermediates.

### Setting up the Docker environment for the server:

1. **Creating the Dockerfile:**
   - A `Dockerfile` is already provided in the `server` directory. Ensure it's configured according to your server needs.

2. **Building the Docker image:**
   - Navigate to the `server` directory where the `Dockerfile` resides.
   - Build the Docker image using:
     ```
     sudo docker build -t your_image_name .
     ```

3. **Viewing Docker images:**
   - To view the list of Docker images present:
     ```
     sudo docker images
     ```

4. **Running the Docker container:**
   - To run the container in the background, listening on port 52423, use:
     ```
     sudo docker run -d -p 52423:52423 your_image_name
     ```

5. **Managing Docker containers:**
   - To view the currently running Docker containers:
     ```
     sudo docker ps
     ```
   - To stop a running Docker container:
     ```
     sudo docker stop CONTAINER_ID_OR_NAME
     ```
   - To remove an image:
     ```
     sudo docker rmi IMAGE_ID_OR_NAME:TAG
     ```

Note: Remember to replace placeholders like `your_image_name`, `CONTAINER_ID_OR_NAME`, and `IMAGE_ID_OR_NAME:TAG` with appropriate values.

