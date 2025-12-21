"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  return (
    <section className="relative py-32 px-6 bg-black overflow-hidden">
      {/* Background Grid */}
      <div
        className="absolute inset-0 opacity-10"
        style={{
          backgroundImage: `linear-gradient(rgba(6,182,212,0.3) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(6,182,212,0.3) 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />

      {/* Gradient Orbs */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-cyan-500/20 to-purple-500/20 rounded-full blur-3xl" />

      <div className="relative max-w-4xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          {/* Glowing Border Card */}
          <div className="relative p-[1px] rounded-3xl bg-gradient-to-r from-cyan-500 via-purple-500 to-pink-500">
            <div className="relative rounded-3xl bg-black/90 backdrop-blur-xl px-8 py-16 md:px-16 md:py-20">
              {/* Inner Glow */}
              <div className="absolute inset-0 rounded-3xl bg-gradient-to-r from-cyan-500/10 via-purple-500/10 to-pink-500/10" />

              <div className="relative z-10">
                <motion.h2
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.2 }}
                  className="text-4xl md:text-5xl lg:text-6xl font-bold text-white mb-6"
                >
                  Ready to Build
                  <br />
                  <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-purple-400">
                    Institutional Memory?
                  </span>
                </motion.h2>

                <motion.p
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.3 }}
                  className="text-gray-400 text-lg md:text-xl mb-10 max-w-2xl mx-auto"
                >
                  Join hundreds of engineering teams who never lose context on
                  their decisions. Start your free trial today.
                </motion.p>

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.4 }}
                  className="flex flex-col sm:flex-row items-center justify-center gap-4"
                >
                  <Link href="/sign-up">
                    <Button
                      size="lg"
                      className="relative group px-10 py-7 text-lg bg-white text-black hover:bg-gray-100 rounded-xl font-semibold"
                    >
                      <span className="flex items-center gap-2">
                        Get Started Free
                        <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                      </span>
                    </Button>
                  </Link>
                  <Link href="#demo">
                    <Button
                      variant="outline"
                      size="lg"
                      className="px-10 py-7 text-lg border-white/20 bg-white/5 hover:bg-white/10 text-white rounded-xl"
                    >
                      Watch Demo
                    </Button>
                  </Link>
                </motion.div>

                {/* Trust Badges */}
                <motion.div
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.6 }}
                  className="mt-12 flex items-center justify-center gap-8 text-gray-500 text-sm"
                >
                  <span>No credit card required</span>
                  <span className="w-1 h-1 rounded-full bg-gray-600" />
                  <span>14-day free trial</span>
                  <span className="w-1 h-1 rounded-full bg-gray-600" />
                  <span>Cancel anytime</span>
                </motion.div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
