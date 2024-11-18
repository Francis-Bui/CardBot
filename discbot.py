import discord
import asyncio
import requests
import json
import os
import time
import re
from dotenv import load_dotenv
from ocr import find_lowest_g_value

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
GUILD_ID = int(os.getenv('GUILD_ID'))
APPLICATION_ID = int(os.getenv('APPLICATION_ID'))
USER_ID = int(os.getenv('USER_ID'))

# Initialize the client for a selfbot
client = discord.Client()

# Headers for the API requests
headers = {
    'Authorization': TOKEN,
    'Content-Type': 'application/json'
}

# Function to send 'sd' message
async def send_message():
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send('sd')
        print("Sent message: sd")

# Function to download and save image attachments
def save_image(url, image_id):
    image_data = requests.get(url).content
    image_filename = f"img/temp_image.webp"
    with open(image_filename, 'wb') as image_file:
        image_file.write(image_data)
    return image_filename

# Function to generate a nonce value
def generate_nonce():
    return str(int(time.time() * 1000))

# Function to click a button
def click_button(message_id, channel_id, custom_id):
    session_id = client.ws.session_id if client.ws else None
    application_id = APPLICATION_ID

    if not session_id:
        print("Error: Missing session_id.")
        return

    if not application_id:
        print("Error: Missing application_id.")
        return

    url = "https://discord.com/api/v10/interactions"
    payload = {
        "type": 3,
        "nonce": generate_nonce(),
        "guild_id": str(GUILD_ID),
        "channel_id": str(channel_id),
        "message_flags": 0,
        "message_id": str(message_id),
        "application_id": str(application_id),
        "session_id": str(session_id),
        "data": {
            "component_type": 2,
            "custom_id": custom_id
        }
    }

    # Send the interaction request
    response = requests.post(url, headers=headers, json=payload)
    print(f"Clicked button with custom_id: {custom_id}, Response: {response.status_code}, Content: {response.text}")

# Function to process SOFI's message for card ID
async def process_sofi_message(message, g_value):
    print(f"Clean message content: {message.clean_content}")

    # Check if the message mentions your user ID
    if f"<@{USER_ID}>" not in message.content:
        print("Message does not mention your user ID. Waiting for the correct message.")
        return

    # Extract the card ID using a regex pattern
    match = re.search(r"`(\w+)`", message.content)
    if match:
        card_id = match.group(1)
        print(f"Extracted card ID: {card_id}")

        channel = client.get_channel(CHANNEL_ID)

        # Celebratory messages based on specific G values
        if g_value == 69:
            await channel.send("nice")
            print("Sent message: nice")
        elif g_value == 420:
            await channel.send("blaze it")
            print("Sent message: blaze it")

        # Check G value and send "sb (ID code)" if G > 50 and not 420
        if g_value > 50 and g_value != 420:
            await channel.send(f"sb {card_id}")
            print(f"Sent message: sb {card_id}")

            # Listen for confirmation buttons from SOFI
            try:
                confirmation_message = await client.wait_for(
                    "message",
                    check=lambda msg: (
                        msg.channel.id == CHANNEL_ID
                        and msg.author.name == 'SOFI'
                        and msg.components
                        and "<@" not in msg.content
                    ),
                    timeout=30
                )
                print("Received confirmation prompt from SOFI.")

                # Use the global APPLICATION_ID to click the button
                application_id = APPLICATION_ID
                if not application_id:
                    print("Error: Missing application_id.")
                    return

                # Click the accept button (first component is usually accept)
                for action_row in confirmation_message.components:
                    for button in action_row.children:
                        if button.custom_id.endswith("_1"):
                            click_button(confirmation_message.id, confirmation_message.channel.id, button.custom_id)
                            print("Card Burned")
                            return

                print("Error: Burn button not found.")
            except asyncio.TimeoutError:
                print("No confirmation prompt received from SOFI.")
        else:
            print(f"G value is {g_value}, no action taken.")
    else:
        print("Error: Could not extract card ID from the message.")


async def process_message(message):
    for attachment in message.attachments:
        content_type = attachment.content_type or ""
        if content_type.startswith("image/"):
            image_filename = save_image(attachment.url, attachment.id)

            lowest_card, lowest_g_value = find_lowest_g_value(image_filename)

            if lowest_card:
                card_index = None
                if lowest_card == "Card 1":
                    card_index = 0
                elif lowest_card == "Card 2":
                    card_index = 1
                elif lowest_card == "Card 3":
                    card_index = 2
                else:
                    print("Error: Invalid card selection.")
                    return

                custom_id = None
                for action_row in message.components:
                    for button in action_row.children:
                        if button.custom_id.endswith(f"_{card_index}"):
                            custom_id = button.custom_id
                            print(f"Selected custom_id: {custom_id}")
                            break

                if not custom_id:
                    print(f"Error: Custom ID for Card {card_index + 1} not found.")
                    return

                # Use the client's application_id to click the button
                click_button(message.id, message.channel.id, custom_id)

                # Wait for SOFI's response after clicking the button
                try:
                    sofi_response = await client.wait_for(
                        "message",
                        check=lambda msg: msg.channel.id == CHANNEL_ID and msg.author.name == 'SOFI' and f"<@{USER_ID}>" in msg.content,
                        timeout=30
                    )
                    print("Received response from SOFI.")
                    await process_sofi_message(sofi_response, lowest_g_value)
                except asyncio.TimeoutError:
                    print("No response from SOFI after clicking the button.")

# Main loop to send 'sd' and listen for a single response
async def main_loop():
    while True:
        await send_message()

        try:
            response_message = await client.wait_for(
                "message",
                check=lambda msg: msg.channel.id == CHANNEL_ID and msg.author.name == 'SOFI' and msg.attachments and f"<@{USER_ID}>" in msg.content,
                timeout=60
            )
            print("Received response from SOFI with attachment.")
            await process_message(response_message)

        except asyncio.TimeoutError:
            print("No response received within the timeout period.")

        await asyncio.sleep(8 * 60)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

    await main_loop()

client.run(TOKEN)