import asyncio
import vertexai
from vertexai import agent_engines
from datetime import datetime, timezone

app = vertexai.agent_engines.get(
    'projects/350875723330/locations/us-central1/reasoningEngines/5452772831257427968'
)

async def query(user_id, session_id, user_query):
    # print(f"user_query: {user_query}")
    text_result = ""
    track = 0
    user_session_list = await app.async_list_sessions(user_id=user_id)
    for user_session in user_session_list["sessions"]:
        if session_id == user_session["id"]:
            print("session_id found")
            async for event in app.async_stream_query(
                user_id=user_id, session_id=session_id, message=user_query
            ):
                print("--------")
                track += 1
                print(f"Event {str(track)}")
                for k in event.keys():
                    print(f"{k}: ", end="")
                    print(event[k])
                print("*******")
            break
    else:
        session = await app.async_create_session(user_id=user_id)
        session_id = session["id"]
        print("new session_id created")
        async for event in app.async_stream_query(
            user_id=user_id, session_id=session["id"], message=user_query
        ):
            print("--------")
            track += 1
            print(f"Event {str(track)}")
            for k in event.keys():
                print(f"{k}: ", end="")
                print(event[k])
            print("*******")
    return session_id, text_result


async def main():
    user_id = "user1"
    session_id = "1"
    user_query = "visualize bar chart for total sales across channel"
    start_time = datetime.now(timezone.utc).isoformat()

    while user_query:
        session_id, res = await query(user_id, session_id, user_query)
        # print(f"res: {res}")
        print(f"session_id: {session_id}")
        user_query=input('>')

    end_time = datetime.now(timezone.utc).isoformat()
    print(f"Session ended. Start: {start_time}, End: {end_time}")


if __name__ == "__main__":
    asyncio.run(main())
