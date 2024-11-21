import discord
import asyncio
import requests
import json
import os
import time
import re
from datetime import datetime, timezone
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

# Stats file
STATS_FILE = "cardbot_stats.json"

# Headers for the API requests
headers = {
    'Authorization': f"{TOKEN}",
    'Content-Type': 'application/json'
}

# Load stats from JSON
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as file:
            return json.load(file)
    else:
        return {
            "lifetime": {"silver": 0, "cubes": 0, "card_drops": 0, "card_burns": 0},
            "daily": {"silver": 0, "cubes": 0, "card_drops": 0, "card_burns": 0},
            "last_drop_time": None,
            "autoburn_enabled": True,
            "autodrop_enabled": True
        }

# Save stats to JSON
def save_stats(stats):
    with open(STATS_FILE, "w") as file:
        json.dump(stats, file, indent=4)

# Initialize stats
stats = load_stats()

# Function to reset daily stats
def reset_daily_stats():
    stats["daily"] = {"silver": 0, "cubes": 0, "card_drops": 0, "card_burns": 0}
    save_stats(stats)
    print("Daily stats reset.")

# Reset daily stats every 24 hours
async def reset_daily_task():
    while True:
        await asyncio.sleep(24 * 60 * 60)  # Wait 24 hours
        reset_daily_stats()

# Function to update stats
def update_stats(reward_type, amount):
    if reward_type in stats["lifetime"]:
        stats["lifetime"][reward_type] += amount
        stats["daily"][reward_type] += amount
        save_stats(stats)
        print(f"Updated stats: +{amount} {reward_type}.")

# Function to send stats
async def send_stats(channel):
    # Get the current UTC time (timezone-aware)
    now = datetime.now(timezone.utc)
    
    # Get the last drop time from stats
    last_drop_time = stats["last_drop_time"]

    if last_drop_time:
        # Convert last_drop_time to a timezone-aware datetime object
        last_drop_time = datetime.fromisoformat(last_drop_time)
        
        # If it's naive (lacking timezone info), make it timezone-aware
        if last_drop_time.tzinfo is None:
            last_drop_time = last_drop_time.replace(tzinfo=timezone.utc)

        # Calculate the time difference
        time_since_last_drop = str(now - last_drop_time).split(".")[0]  # Remove microseconds
    else:
        time_since_last_drop = "N/A"

    # Get the status of autoburn and autodrop
    autoburn_status = "enabled" if stats["autoburn_enabled"] else "disabled"
    autodrop_status = "enabled" if stats["autodrop_enabled"] else "disabled"

    # Prepare and send the stats message
    message = (
        f"```\n"
        f"CardBot Stats\n"
        f"--------------\n"
        f"Lifetime Stats:\n"
        f"  Cards Dropped: {stats['lifetime']['card_drops']}\n"
        f"  Cards Burned: {stats['lifetime']['card_burns']}\n\n"
        f"Daily Stats:\n"
        f"  Cards Dropped: {stats['daily']['card_drops']}\n"
        f"  Cards Burned: {stats['daily']['card_burns']}\n\n"
        f"Time Since Last Drop: {time_since_last_drop}\n"
        f"Autoburn: {autoburn_status}\n"
        f"Autodrop: {autodrop_status}\n"
        f"```"
    )
    await channel.send(message)

# Function to send 'sd' message
async def send_message():
    if stats["autodrop_enabled"]:
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send('sd')
            print("Sent message: sd")
    else:
        print("Autodrop is disabled. Skipping 'sd' message.")

# Function to download and save image attachments
def save_image(url, image_id):
    image_data = requests.get(url).content
    image_filename = f"img/temp_image.webp"
    with open(image_filename, 'wb') as image_file:
        image_file.write(image_data)
    return image_filename

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
        "nonce": str(int(time.time() * 1000)),
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

# Function to process SOFI's card burn response
async def process_sofi_burn_response(card_id):
    global stats

    # Check if autoburn is enabled
    if not stats["autoburn_enabled"]:
        print("Autoburn is disabled. Skipping card burn.")
        return

    # Step 1: Send "sb (card_id)" message
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"sb {card_id}")
        print(f"Sent message: sb {card_id}")

    # Step 2: Wait for SOFI's burn message with buttons
    try:
        burn_message = await client.wait_for(
            "message",
            check=lambda msg: (
                msg.channel.id == CHANNEL_ID
                and msg.author.name == 'SOFI'
                and msg.components  # Message should contain buttons
            ),
            timeout=30
        )
        print("Received burn message from SOFI.")
    except asyncio.TimeoutError:
        print("No burn message received from SOFI.")
        return

    # Step 3: Click the burn button (green button)
    try:
        for action_row in burn_message.components:
            for button in action_row.children:
                if button.custom_id.endswith("_0"):  # Assuming "_0" is the burn button
                    click_button(burn_message.id, burn_message.channel.id, button.custom_id)
                    print("Clicked burn button.")
                    break
            else:
                continue
            break
        else:
            print("Error: Burn button not found.")
            return
    except Exception as e:
        print(f"Error clicking burn button: {e}")
        return

    # Increment card burns in stats
    update_stats("card_burns", 1)
    print(f"Card successfully burned.")

# Function to process SOFI's card drop response
async def process_message(message):
    global stats

    for attachment in message.attachments:
        content_type = attachment.content_type or ""
        if content_type.startswith("image/"):
            image_filename = save_image(attachment.url, attachment.id)

            # Determine the lowest G value using OCR
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

                # Use the application's ID to click the button
                click_button(message.id, message.channel.id, custom_id)

                # Wait for SOFI's response after clicking the button
                try:
                    sofi_response = await client.wait_for(
                        "message",
                        check=lambda msg: (
                            msg.channel.id == CHANNEL_ID
                            and msg.author.name == 'SOFI'
                            and f"<@{USER_ID}>" in msg.content
                        ),
                        timeout=30
                    )
                    print("Received response from SOFI.")

                    # Extract card ID and process burn
                    match = re.search(r"`(\w+)`", sofi_response.content)
                    if match:
                        card_id = match.group(1)
                        print(f"Extracted card ID: {card_id}")
                        await process_sofi_burn_response(card_id)
                    else:
                        print("Error: Could not extract card ID from the message.")
                except asyncio.TimeoutError:
                    print("No response from SOFI after clicking the button.")

# Command listener to handle stats and toggle autoburn/autodrop
@client.event
async def on_message(message):
    if message.author.id != USER_ID:
        return

    if message.content.lower() == "autoburn off":
        stats["autoburn_enabled"] = False
        save_stats(stats)
        await message.channel.send("```[autoburning disabled]```")
    elif message.content.lower() == "autoburn on":
        stats["autoburn_enabled"] = True
        save_stats(stats)
        await message.channel.send("```[autoburning enabled]```")
    elif message.content.lower() == "autodrop off":
        stats["autodrop_enabled"] = False
        save_stats(stats)
        await message.channel.send("```[autodrop disabled]```")
    elif message.content.lower() == "autodrop on":
        stats["autodrop_enabled"] = True
        save_stats(stats)
        await message.channel.send("```[autodrop enabled]```")
    elif message.content.lower() == "cardbot stats":
        await send_stats(message.channel)

# Main loop to send 'sd' and listen for a single response
async def main_loop():
    while True:
        if stats["autodrop_enabled"]:
            await send_message()

        try:
            response_message = await client.wait_for(
                "message",
                check=lambda msg: msg.channel.id == CHANNEL_ID and msg.author.name == 'SOFI' and msg.attachments and f"<@{USER_ID}>" in msg.content,
                timeout=60
            )
            print("Received response from SOFI with attachment.")
            stats["last_drop_time"] = datetime.utcnow().isoformat()
            update_stats("card_drops", 1)
            save_stats(stats)
            await process_message(response_message)
        except asyncio.TimeoutError:
            print("No response received within the timeout period.")

        await asyncio.sleep(8 * 60)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(reset_daily_task())
    await main_loop()

client.run(TOKEN)