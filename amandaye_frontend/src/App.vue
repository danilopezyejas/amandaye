<template>
  <div class="min-h-screen relative font-sans text-white overflow-hidden">
    <!-- Background Image -->
    <div class="absolute inset-0 z-0">
      <img 
        src="/fondo.png" 
        alt="Background Kayak" 
        class="w-full h-full object-cover"
      />
      <div class="absolute inset-0 bg-gradient-to-b from-blue-900/60 via-blue-900/40 to-blue-900/80 backdrop-blur-[2px]"></div>
    </div>

    <!-- Content Wrapper -->
    <div class="relative z-10 flex flex-col min-h-screen">
      
      <!-- Header -->
      <header class="w-full py-2">
        <div class="container mx-auto px-6 flex justify-between items-center">
          <div class="flex items-center gap-4 group cursor-pointer">
            <div class="relative">
              <div class="absolute inset-0 bg-orange-500 rounded-full blur opacity-50 group-hover:opacity-100 transition-opacity duration-300"></div>
              <img src="/logo.svg" alt="Club Amandayé Logo" class="h-14 w-14 relative z-10 drop-shadow-lg transform group-hover:scale-110 transition-transform duration-300" />
            </div>
            <div>
              <h1 class="text-2xl font-black tracking-tight drop-shadow-md text-orange-400">AMANDAYÉ IPEGUÁ</h1>
              <p class="text-xs font-medium text-blue-200 tracking-widest uppercase">Paysandú • Uruguay</p>
            </div>
          </div>
          <!-- Nav -->
          <a
            href="http://localhost:8000/admin/"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-3 text-sm font-bold uppercase tracking-wider text-white hover:text-orange-300 transition-all border-2 border-orange-500/70 hover:border-orange-400 px-2 py-2 rounded-full bg-orange-600/30 hover:bg-orange-600/50 shadow-lg shadow-orange-900/30"
          >
           Acceder
          </a>
        </div>
      </header>

      <!-- Main Content -->
      <main class="flex-grow flex flex-col items-center justify-center px-4 py-8 text-center">
        
        <transition name="fade" mode="out-in">
          <!-- Hero View -->
          <div v-if="!showForm" class="max-w-4xl space-y-8" key="hero">
            <div class="space-y-4 animate-fade-in-up">
              <span class="inline-block py-2 px-2 rounded-full bg-orange-500/20 border border-orange-500/50 text-orange-300 text-sm font-bold tracking-wider uppercase mb-4 backdrop-blur-md">
                Temporada 2026
              </span>
              <h2 class="text-5xl md:text-7xl font-black leading-tight drop-shadow-2xl">
                DOMINÁ EL <br/>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-red-500">RÍO URUGUAY</span>
              </h2>
              <p class="text-xl md:text-2xl text-blue-100 max-w-2xl mx-auto font-light leading-relaxed drop-shadow-md">
                Unite a la comunidad más apasionada del remo y canotaje. 
                Naturaleza, adrenalina y amistad en cada palada.
              </p>
            </div>

            <div class="pt-8 animate-fade-in-up delay-200">
              <button
                @click="showForm = true"
                class="group relative inline-flex items-center justify-center px-2 py-2 text-2xl font-black text-white transition-all duration-200 bg-orange-600 font-pj rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-600 hover:bg-orange-500 hover:scale-110 shadow-[0_0_40px_rgba(234,88,12,0.6)] cursor-pointer"
              >
                <span class="mr-2">HACETE SOCIO HOY</span>
                <svg class="w-5 h-5 transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
                </svg>
                <div class="absolute -inset-3 rounded-full bg-orange-400 opacity-20 group-hover:opacity-40 blur-lg transition-opacity duration-200"></div>
              </button>
              <p class="mt-4 text-sm text-blue-300 font-medium">¡Primera clase de prueba gratis!</p>
            </div>
          </div>

          <!-- Registration Form View -->
          <RegistrationForm v-else @close="showForm = false" key="form" />
        </transition>

        <!-- Map Modal -->
        <transition name="fade">
          <div v-if="showMap" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" @click.self="showMap = false">
            <div class="relative w-full max-w-4xl bg-white rounded-2xl overflow-hidden shadow-2xl animate-scale-in">
              <button @click="showMap = false" class="absolute top-4 right-4 z-10 p-2 bg-white/90 rounded-full hover:bg-white text-gray-800 shadow-md transition-all hover:scale-110">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
              <div class="aspect-video w-full">
                <iframe 
                  src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3372.3407991154763!2d-58.09040793124389!3d-32.302696725655174!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x95afcbf480220695%3A0xe9d737521ba84bd!2zQW1hbmRhecOpIElwZWd1w6E!5e0!3m2!1ses!2suy!4v1764852307534!5m2!1ses!2suy" 
                  width="100%" 
                  height="100%" 
                  style="border:0;" 
                  allowfullscreen="" 
                  loading="lazy" 
                  referrerpolicy="no-referrer-when-downgrade">
                </iframe>
              </div>
            </div>
          </div>
        </transition>

      </main>

      <!-- Footer -->
      <footer class="w-full py-2 border-t border-white/10 bg-black/20 backdrop-blur-sm">
        <div class="container mx-auto px-2 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-blue-200">
          <div class="flex flex-col md:flex-row items-center gap-2 md:gap-6">
            <button @click="showMap = true" class="flex items-center gap-2 hover:text-orange-400 transition-colors group cursor-pointer">
              <svg class="w-4 h-4 text-orange-500 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
              <span class="border-b border-transparent group-hover:border-orange-400">Paysandú, Uruguay</span>
            </button>
            <span class="flex items-center gap-2">
              <svg class="w-4 h-4 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
              amandaye.ipegua@gmail.com
            </span>
            <a href="https://wa.me/59891625775" target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 hover:text-orange-400 transition-colors group">
              <svg class="w-4 h-4 text-orange-500 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
              091 625 775
            </a>
          </div>
          <div class="flex gap-6">
            <a href="https://www.instagram.com/amandaye_ipegua" target="_blank" rel="noopener noreferrer" class="hover:text-orange-400 transition-colors font-semibold uppercase tracking-wider text-xs">Instagram</a>
            <a href="https://www.facebook.com/amandaye.ipegua" target="_blank" rel="noopener noreferrer" class="hover:text-orange-400 transition-colors font-semibold uppercase tracking-wider text-xs">Facebook</a>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import RegistrationForm from './components/RegistrationForm.vue'

const showForm = ref(false)
const showMap = ref(false)
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.animate-fade-in-up {
  animation: fadeInUp 0.8s ease-out forwards;
}

.delay-200 {
  animation-delay: 0.2s;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-scale-in {
  animation: scaleIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
