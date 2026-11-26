import argparse, asyncio, json, uuid
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition
from app.core.config import settings
from app.workers.document_worker import validate_event

async def read_dlq(limit: int):
    consumer=AIOKafkaConsumer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, enable_auto_commit=False, auto_offset_reset="earliest")
    await consumer.start()
    try:
        partitions=await consumer.partitions_for_topic(settings.KAFKA_DOCUMENT_DLQ_TOPIC)
        if not partitions: return []
        assigned={TopicPartition(settings.KAFKA_DOCUMENT_DLQ_TOPIC,p) for p in partitions}
        consumer.assign(assigned)
        await consumer.seek_to_beginning(*assigned)
        ends=await consumer.end_offsets(assigned)
        found=[]
        while True:
            remaining=False
            for tp in assigned:
                if await consumer.position(tp) < ends[tp]:
                    remaining=True
                    break
            if not remaining: break
            batches=await consumer.getmany(timeout_ms=1000,max_records=max(1,min(100,limit-len(found))))
            for messages in batches.values():
                for msg in messages:
                    try: found.append(json.loads(msg.value.decode("utf-8")))
                    except Exception: found.append({"malformed": True, "offset": msg.offset})
                    if len(found)>=limit: return found
        return found
    finally: await consumer.stop()

async def replay(event_id: str):
    wanted=str(uuid.UUID(event_id)); entries=await read_dlq(1000)
    match=None
    for item in entries:
        original=item.get("original_event") if isinstance(item,dict) else None
        if isinstance(original,dict) and str(original.get("event_id"))==wanted:
            match=original; break
    if match is None: raise SystemExit("DLQ event id not found in the first 1000 records.")
    validate_event(match)
    producer=AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v,separators=(",",":"),ensure_ascii=False).encode("utf-8"), acks="all", enable_idempotence=True)
    await producer.start()
    try: await producer.send_and_wait(settings.KAFKA_DOCUMENT_TOPIC,match,key=match["document_id"].encode("utf-8"))
    finally: await producer.stop()
    print(f"Replayed event {wanted} to {settings.KAFKA_DOCUMENT_TOPIC}; consumer offsets were not changed.")

async def main():
    parser=argparse.ArgumentParser(description="Read-only DLQ inspection and explicitly confirmed replay")
    parser.add_argument("--list",action="store_true")
    parser.add_argument("--limit",type=int,default=20)
    parser.add_argument("--event-id")
    parser.add_argument("--confirm-replay",action="store_true")
    args=parser.parse_args()
    if args.event_id:
        if not args.confirm_replay: raise SystemExit("Replay requires --confirm-replay")
        await replay(args.event_id)
    else:
        rows=await read_dlq(max(1,min(args.limit,1000)))
        for row in rows: print(json.dumps(row,ensure_ascii=False))
        print(f"Displayed {len(rows)} DLQ record(s). No offsets committed.")
if __name__=="__main__": asyncio.run(main())
