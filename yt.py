import os
import time
import requests
from moviepy.editor import VideoFileClip
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext

# Global storage for progress
progress_data = {}


def estimate_processing_time(video_path):
    """Estimate processing time based on video duration."""
    clip = VideoFileClip(video_path)
    duration = clip.duration  # Duration in seconds
    processing_speed = 2  # Assume 2 seconds of video processed per second
    clip.close()
    return duration / processing_speed


def download_video(url, output_path):
    """Download video from the given URL."""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(output_path, 'wb') as file:
        for data in response.iter_content(1024):
            file.write(data)
            downloaded += len(data)
    return output_path


def process_video(input_path, output_path, chat_id):
    """Process the video: crop to portrait and shorten."""
    global progress_data

    clip = VideoFileClip(input_path)
    duration = clip.duration
    short_duration = min(duration, 15)  # Clip to 15 seconds

    start_time = time.time()

    def update_progress(current_time):
        elapsed = time.time() - start_time
        percentage = (current_time / short_duration) * 100
        remaining_time = (elapsed / (percentage / 100)) - elapsed if percentage > 0 else short_duration
        progress_data[chat_id] = {"percentage": percentage, "remaining_time": remaining_time}

    short_clip = clip.subclip(0, short_duration)
    portrait_clip = short_clip.resize(height=1080).crop(x_center=short_clip.w / 2, width=1080, height=1920)

    portrait_clip.write_videofile(
        output_path,
        codec="libx264",
        logger=None,
        progress_bar=False,
        callback=lambda t: update_progress(t)
    )

    progress_data[chat_id] = {"percentage": 100, "remaining_time": 0}
    clip.close()


async def start(update: Update, context: CallbackContext):
    """Handle the /start command."""
    await update.message.reply_text(
        "Welcome! Send me a video link to process it into a YouTube Short."
    )


async def handle_video_link(update: Update, context: CallbackContext):
    """Handle video links sent by the user."""
    global progress_data

    video_url = update.message.text.strip()
    chat_id = update.message.chat_id

    # Download video
    await update.message.reply_text("Downloading video...")
    input_path = f"./{chat_id}_input.mp4"
    try:
        download_video(video_url, input_path)
    except Exception as e:
        await update.message.reply_text(f"Failed to download the video: {str(e)}")
        return

    # Estimate processing time
    estimated_time = estimate_processing_time(input_path)
    await update.message.reply_text(
        f"Video downloaded! Estimated processing time: {round(estimated_time, 2)} seconds."
    )

    # Start processing
    output_path = f"./{chat_id}_output.mp4"
    progress_data[chat_id] = {"percentage": 0, "remaining_time": estimated_time}
    await update.message.reply_text("Processing started...")

    def send_progress_updates():
        while progress_data[chat_id]["percentage"] < 100:
            percentage = progress_data[chat_id]["percentage"]
            remaining_time = progress_data[chat_id]["remaining_time"]
            context.bot.send_message(
                chat_id,
                f"Processing: {round(percentage, 2)}% complete. Remaining time: {round(remaining_time, 2)} seconds."
            )
            time.sleep(5)

    # Send progress updates in a separate thread
    from threading import Thread
    Thread(target=send_progress_updates).start()

    try:
        process_video(input_path, output_path, chat_id)
    except Exception as e:
        await update.message.reply_text(f"Error during processing: {str(e)}")
        return

    # Send processed video
    await update.message.reply_text("Processing complete! Sending your video...")
    with open(output_path, 'rb') as file:
        await update.message.reply_video(file)

    # Cleanup
    os.remove(input_path)
    os.remove(output_path)


# Main function to set up the bot
def main():
    # Initialize the bot
    app = ApplicationBuilder().token("8029801448:AAGT9J1CPOLvI3iJ76wDKF72b3uMxQCVqp4").build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_video_link))

    # Run the bot
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
