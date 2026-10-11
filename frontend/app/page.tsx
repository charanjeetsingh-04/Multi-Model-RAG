import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Landing() {
  return (
    <section className="max-w-5xl mx-auto px-6 py-20">
      <div className="text-center space-y-6">
        <h1 className="text-5xl font-bold tracking-tight">
          Chat with <span className="text-primary underline decoration-wavy">your videos</span>.
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Upload a video. We transcribe, chunk, embed, and let you converse with it using Gemini 2.5 Flash
          and a hybrid RAG pipeline with citations.
        </p>
        <div className="flex justify-center gap-3 pt-4">
          <Link href="/register"><Button size="lg">Get started</Button></Link>
          <Link href="/login"><Button variant="outline" size="lg">Login</Button></Link>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6 mt-20">
        {[
          { title: "Audio → Text", body: "FFmpeg + Whisper transcribes with timestamps." },
          { title: "Semantic Retrieval", body: "Hybrid dense+sparse retrieval, reranked." },
          { title: "Cited Answers", body: "Every claim shows a clickable timestamp." }
        ].map((f) => (
          <div key={f.title} className="rounded-lg border border-border p-6">
            <h3 className="font-semibold mb-2">{f.title}</h3>
            <p className="text-sm text-muted-foreground">{f.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
