import asyncio
import vertexai
from vertexai import agent_engines
from datetime import datetime, timezone
 
app = vertexai.agent_engines.get(
    'projects/350875723330/locations/us-central1/reasoningEngines/4455295882539040768'
)
 
async def query(user_id, session_id, user_query):
    text_result = ""
    track = 0
    user_session_list = await app.async_list_sessions(user_id=user_id)
 
    for user_session in user_session_list.get("sessions", []):
        if session_id == user_session["id"]:
            print("session_id found")
            async for event in app.async_stream_query(
                user_id=user_id, session_id=session_id, message=user_query
            ):
                track += 1
                print(f"--------\nEvent {track}")
                for k in event.keys():
                  print(f"{k}: ",end = "")
                  print(event[k])
                # Print only the text part
                for part in event.get("content", {}).get("parts", []):
                    if "text" in part:
                        print(part["text"])
                print("*******")
            break
    else:
        session = await app.async_create_session(user_id=user_id)
        session_id = session["id"]
        print("new session_id created")
        async for event in app.async_stream_query(
            user_id=user_id, session_id=session_id, message=user_query
        ):
            track += 1
            print(f"--------\nEvent {track}")
            for k in event.keys():
                  print(f"{k}: ",end = "")
                  print(event[k])
            for part in event.get("content", {}).get("parts", []):
                if "text" in part:
                    print(part["text"])
            print("*******")
 
    return session_id, text_result
 
 
async def main():
    user_id = "user1"
    session_id = "1"
    user_query = "Based on last month, which campaign performed better — CMP_2025_0067 or CMP_2025_0001 — when looking at budget and impressions? Give me the reason too."
    start_time = datetime.now(timezone.utc)
 
    while user_query:
        
        session_id, res = await query(user_id, session_id, user_query)
        print(f"session_id: {session_id}")
        user_query = input('>')

 
        end_time = datetime.now(timezone.utc)
        latency_secs = (end_time - start_time).total_seconds()
        print(f"Session ended. Start: {start_time}, End: {end_time}\nLatency_secs: {latency_secs}")
        start_time = datetime.now(timezone.utc)
 
if __name__ == "__main__":
    asyncio.run(main())