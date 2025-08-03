<template>
  <div>
    <header class="bg-azul-institucional text-white p-5 flex items-center justify-center gap-4">
      <img src="/logo.png" alt="Logo del Club Amandayé" class="h-12 w-12 object-contain" />
      <h1 class="text-3xl font-bold m-0">Club Amandayé Ipegua</h1>
    </header>
    <nav class="flex justify-center gap-4 py-2 bg-azul-marino">
      <a href="#inicio" class="text-white font-bold">Inicio</a>
      <a href="#club" class="text-white font-bold">El Club</a>
      <a href="#socios" class="text-white font-bold">Hacete Socio</a>
      <a href="#actividades" class="text-white font-bold">Actividades</a>
      <a href="#calendario" class="text-white font-bold">Calendario</a>
      <a href="#contacto" class="text-white font-bold">Contacto</a>
    </nav>
    <section class="hero bg-celeste py-16 text-center">
      <h2 class="text-2xl font-semibold mb-4">Vení a remar con nosotros</h2>
      <button class="bg-naranja-acento text-white px-5 py-2 rounded">Hacete socio</button>
    </section>
    <section class="section py-10 text-center" id="club">
      <h2 class="text-xl font-bold mb-6">¿Quiénes somos?</h2>
      <div class="cards flex flex-wrap justify-center gap-5">
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">
          <h3 class="font-bold mb-2">Nuestra historia</h3>
          <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
        </div>
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">
          <h3 class="font-bold mb-2">Valores</h3>
          <p>Espíritu de grupo, respeto, sostenibilidad.</p>
        </div>
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">
          <h3 class="font-bold mb-2">Nuestra sede</h3>
          <p>Ubicada en la costa del río Uruguay.</p>
        </div>
      </div>
    </section>
    <section class="section py-10 text-center">
      <h2 class="text-xl font-bold mb-4">Próxima travesía: sábado 14 de julio</h2>
      <button class="bg-coral text-white px-5 py-2 rounded">Ver más</button>
    </section>
    <section class="section py-10 text-center" id="actividades">
      <h2 class="text-xl font-bold mb-6">Actividades</h2>
      <div class="cards flex flex-wrap justify-center gap-5">
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">Canotaje Travesías</div>
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">Kayak</div>
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">Eventos</div>
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">Yoga</div>
        <div class="card w-44 bg-gris-claro p-4 border border-azul-secundario rounded">Funcional</div>
      </div>
    </section>
    <section class="section py-10 text-center">
      <h2 class="text-xl font-bold mb-4">Condiciones actuales</h2>
      <div class="info-box inline-block m-2 p-2 bg-celeste rounded">Altura del río: 2.87 m</div>
      <div class="info-box inline-block m-2 p-2 bg-celeste rounded">Clima: 24º - Estable</div>
    </section>
    <section class="section py-10 text-center">
      <h2 class="text-xl font-bold mb-4">¡Hacete socio!</h2>
      <p class="mb-4">Sumate al Club Amandayé y descubrí la aventura.</p>
      <button class="bg-coral text-white px-5 py-2 rounded">Comenzar inscripción</button>
    </section>
    <footer class="bg-azul-institucional text-white p-5 text-center">
      <img src="/logo.png" alt="Logo del Club Amandayé" class="max-h-16 mb-2 mx-auto" />
      <p>Club Amandayé Ipegua - Paysandú, Uruguay</p>
    </footer>
  </div>
</template>

<script setup>
// No hay lógica JS por ahora
</script>

<style>
:root {
  --azul-institucional: #001d63;
  --azul-secundario: #1133a1;
  --amarillo-acento: #ffd600;
  --naranja-acento: #ff7a00;
  --azul-marino: #002147;
  --celeste: #a5c8e1;
  --arena: #f1e9d2;
  --coral: #ff5c5c;
  --gris-claro: #f4f4f4;
  --blanco: #ffffff;
}
.bg-azul-institucional { background-color: var(--azul-institucional); }
.bg-azul-marino { background-color: var(--azul-marino); }
.bg-celeste { background-color: var(--celeste); }
.bg-naranja-acento { background-color: var(--naranja-acento); }
.bg-gris-claro { background-color: var(--gris-claro); }
.bg-coral { background-color: var(--coral); }
.text-white { color: var(--blanco); }
.text-azul-marino { color: var(--azul-marino); }
.border-azul-secundario { border-color: var(--azul-secundario); }
</style>
