"use client";

import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { newSessionId, sendChatMessage } from "../lib/api";

interface Message {
  id: string;
  text: string;
  sender: "user" | "nexus";
  verified?: boolean;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      text: "Olá! Sou a Nexus-Alpha. Como posso ajudar você hoje com base nos meus dados verificados?",
      sender: "nexus",
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [step, setStep] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const sessionRef = useRef<string>("");

  useEffect(() => {
    sessionRef.current = newSessionId();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSendMessage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isTyping) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      text: input,
      sender: "user",
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);
    setStep("Nexus pensando...");

    try {
      const data = await sendChatMessage(userMsg.text, sessionRef.current);
      setStep(data.reasoning_steps?.[data.reasoning_steps.length - 1] ?? "");
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text:
            data.reply ||
            "Desculpe, tive uma instabilidade temporária no meu link de comunicação.",
          sender: "nexus",
          verified: data.verified ?? false,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: "err",
          text: "Erro ao conectar com o Córtex Central.",
          sender: "nexus",
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-sans text-slate-100">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85, y: 50 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: 30 }}
            transition={{ type: "spring", stiffness: 120, damping: 16 }}
            className="w-[350px] sm:w-[380px] h-[500px] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden mb-4"
          >
            <div className="bg-slate-950 p-4 border-b border-slate-800 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-violet-500 animate-pulse" />
                <div>
                  <h3 className="text-sm font-bold text-white">Nexus Assistente</h3>
                  <p className="text-[10px] text-slate-400 font-mono">AGENTE INTEGRADO</p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-white transition-colors text-sm"
                aria-label="Fechar chat"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-slate-900/50">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                      msg.sender === "user"
                        ? "bg-violet-600 text-white rounded-tr-none"
                        : "bg-slate-800 text-slate-200 rounded-tl-none border border-slate-700/50"
                    }`}
                  >
                    {msg.text}
                    {msg.sender === "nexus" && msg.verified && (
                      <span className="mt-1.5 flex w-fit items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                        ✓ Fato Verificado
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {isTyping && (
                <div className="flex flex-col gap-1.5">
                  {step && (
                    <span className="text-[10px] font-mono text-violet-300">{step}</span>
                  )}
                  <div className="flex justify-start">
                    <div className="bg-slate-800 border border-slate-700/50 rounded-2xl rounded-tl-none px-4 py-3 flex space-x-1 items-center animate-pulse">
                      <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:300ms]" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <form
              onSubmit={handleSendMessage}
              className="p-3 bg-slate-950 border-t border-slate-800 flex gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Pergunte ao Córtex da IA..."
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-violet-500 transition-colors placeholder:text-slate-500"
              />
              <button
                type="submit"
                disabled={isTyping || !input.trim()}
                className="bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 rounded-xl text-sm font-medium transition-colors"
              >
                Enviar
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(!isOpen)}
        className="h-14 w-14 bg-violet-600 hover:bg-violet-500 rounded-full shadow-xl flex items-center justify-center text-2xl text-white border border-violet-400/20"
        aria-label={isOpen ? "Fechar chat" : "Abrir chat da Nexus-Alpha"}
      >
        💬
      </motion.button>
    </div>
  );
}
