import type { StreamEvent } from "../../lib/sseClient";
import { EventTimeline } from "../debug/EventTimeline";

export function PlatformEvidence({ events }: { events: StreamEvent[] }) {
  return <EventTimeline events={events} />;
}
