<template>
  <div class="w-full max-w-xl relative mx-auto" key="form">
    <!-- Glass Card Base -->
    <div class="absolute inset-0 bg-white/10 backdrop-blur-xl rounded-3xl transform rotate-1 scale-105 hidden md:block"></div>
    <div class="relative bg-black/60 md:bg-black/40 backdrop-blur-md border border-white/10 p-6 md:p-10 rounded-3xl shadow-2xl animate-scale-in">
      
      <!-- Header y Botón Cerrar -->
      <div class="flex justify-between items-start mb-6">
        <div>
          <h3 class="text-2xl font-bold text-white">Inscripción</h3>
          <p class="text-blue-200 text-sm">
            <span v-if="step === 1">Paso 1: Tipo de Membresía</span>
            <span v-else-if="step === 2">Paso 2: Datos Personales</span>
            <span v-else-if="step === 3">Paso 3: Núcleo Familiar</span>
            <span v-else>Paso 4: Confirmación</span>
          </p>
        </div>
        <button @click="$emit('close')" class="p-2 rounded-full bg-white/10 hover:bg-white/25 transition-colors text-white/70 hover:text-white border border-white/10 hover:border-white/30">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
      </div>

      <!-- Barra de progreso simple -->
      <div class="w-full bg-white/10 rounded-full h-1.5 mb-8">
        <div class="bg-orange-500 h-1.5 rounded-full transition-all duration-300" :style="{ width: `${(step / totalSteps) * 100}%` }"></div>
      </div>

      <!-- Mensajes de Error (Validación de Backend) -->
      <div v-if="apiError" class="mb-4 bg-red-500/20 border border-red-500/50 text-red-200 px-4 py-3 rounded-xl text-sm font-medium">
        {{ apiError }}
      </div>

      <!-- PASO 1: Tipo de Afiliación -->
      <div v-if="step === 1" class="space-y-6 text-left animate-fade-in-up">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button 
            @click="formType = 'INDIVIDUAL'; nextStep()"
            class="flex flex-col items-center justify-center p-6 bg-white/5 border-2 rounded-2xl transition-all hover:bg-white/10"
            :class="formType === 'INDIVIDUAL' ? 'border-orange-500 shadow-[0_0_15px_rgba(234,88,12,0.3)]' : 'border-white/10'"
          >
            <svg class="w-12 h-12 text-orange-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
            <span class="font-bold text-lg text-white">Socio Individual</span>
            <span class="text-xs text-blue-200 mt-1 text-center">Para una sola persona. Acceso total a las instalaciones.</span>
          </button>
          
          <button 
            @click="formType = 'FAMILIAR'; nextStep()"
            class="flex flex-col items-center justify-center p-6 bg-white/5 border-2 rounded-2xl transition-all hover:bg-white/10"
            :class="formType === 'FAMILIAR' ? 'border-orange-500 shadow-[0_0_15px_rgba(234,88,12,0.3)]' : 'border-white/10'"
          >
            <svg class="w-12 h-12 text-orange-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
            <span class="font-bold text-lg text-white">Socio Familiar</span>
            <span class="text-xs text-blue-200 mt-1 text-center">Incluye titular, pareja y hasta 2 hijos menores de 18 años.</span>
          </button>
        </div>
      </div>

      <!-- PASO 2: Datos Titular -->
      <form v-if="step === 2" @submit.prevent="nextStep" class="space-y-4 text-left animate-fade-in-up">
        
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Primer Nombre *</label>
            <input type="text" v-model="titular.PrimerNombre" class="input-field" required />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Segundo Nombre</label>
            <input type="text" v-model="titular.SegundoNombre" class="input-field" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Primer Apellido *</label>
            <input type="text" v-model="titular.PrimerApellido" class="input-field" required />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Segundo Apellido</label>
            <input type="text" v-model="titular.SegundoApellido" class="input-field" />
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Cédula *</label>
            <input type="text" v-model="titular.Cedula" class="input-field" placeholder="Sin puntos ni guiones" required />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Fecha Nacimiento * (Mínimo 18 años)</label>
            <input type="date" v-model="titular.FechaNacimiento" class="input-field [color-scheme:dark]" required />
          </div>
        </div>

        <div class="space-y-1">
          <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Dirección *</label>
          <input type="text" v-model="titular.Direccion" class="input-field" required />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div class="space-y-1 sm:col-span-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Celular *</label>
            <input type="tel" v-model="titular.Celular" class="input-field" placeholder="Ej: 099123456" required />
          </div>
          <div class="space-y-1 sm:col-span-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Prestador de Salud</label>
            <input type="text" v-model="titular.salud" class="input-field" placeholder="Ej: COMEPA" />
          </div>
          <div class="space-y-1 sm:col-span-1">
            <label class="text-xs font-bold text-blue-300 uppercase tracking-wider ml-1">Email</label>
            <input type="email" v-model="titular.Correo" class="input-field" />
          </div>
        </div>

        <div class="flex justify-between mt-6 pt-4 border-t border-white/10">
          <button type="button" @click="prevStep" class="btn-secondary">Atrás</button>
          <button type="submit" class="btn-primary">Continuar</button>
        </div>
      </form>

      <!-- PASO 3: Familiares -->
      <div v-if="step === 3" class="space-y-4 text-left animate-fade-in-up">
        <p class="text-xs text-blue-200 bg-blue-900/40 p-3 rounded-lg border border-blue-500/30">
          Puedes agregar hasta 1 pareja/tutor y 2 hijos menores de edad. Pasa al resumen si no deseas agregar a nadie más.
        </p>

        <!-- Lista de Familiares -->
        <div v-for="(fam, index) in familiares" :key="index" class="bg-white/5 border border-white/10 p-4 rounded-xl relative">
          <button @click="removeFamiliar(index)" class="absolute top-2 right-2 text-white/50 hover:text-red-400 p-1">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
          </button>
          
          <p class="font-bold text-orange-400 mb-2 border-b border-white/10 pb-1 flex gap-2">
            Integrante {{ index + 1 }}
          </p>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
            <div class="space-y-1">
              <label class="text-[10px] font-bold text-blue-300 uppercase">Parentesco</label>
              <select v-model="fam.relacionTitular" class="input-field py-2 text-sm bg-gray-900">
                <option value="PAREJA">Pareja / Esposo/a</option>
                <option value="HIJO">Hijo/a</option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="text-[10px] font-bold text-blue-300 uppercase">Cédula</label>
              <input type="text" v-model="fam.Cedula" class="input-field py-2 text-sm" required />
            </div>
            <div class="space-y-1">
              <label class="text-[10px] font-bold text-blue-300 uppercase">Primer Nombre</label>
              <input type="text" v-model="fam.PrimerNombre" class="input-field py-2 text-sm" required />
            </div>
            <div class="space-y-1">
              <label class="text-[10px] font-bold text-blue-300 uppercase">Primer Apellido</label>
              <input type="text" v-model="fam.PrimerApellido" class="input-field py-2 text-sm" required />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <label class="text-[10px] font-bold text-blue-300 uppercase">Fecha Nacimiento</label>
              <input type="date" v-model="fam.FechaNacimiento" class="input-field py-2 text-sm [color-scheme:dark]" required />
            </div>
          </div>
        </div>

        <button 
          v-if="familiares.length < 3" 
          @click="addFamiliar"
          class="w-full border-2 border-dashed border-white/20 text-white/70 hover:bg-white/5 hover:border-orange-500 hover:text-orange-400 py-3 rounded-xl font-medium transition-all text-sm flex items-center justify-center gap-2"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
          Añadir Integrante Familiar
        </button>

        <div class="flex justify-between mt-8 pt-4 border-t border-white/10">
          <button @click="prevStep" class="btn-secondary">Atrás</button>
          <button @click="validateFamiliares" class="btn-primary">Continuar al Resumen</button>
        </div>
      </div>

      <!-- PASO 4: Resumen y Envío -->
      <div v-if="step === 4" class="space-y-4 text-left animate-fade-in-up">
        
        <div class="bg-black/40 rounded-xl p-4 border border-white/10 text-sm">
          <h4 class="font-bold text-orange-400 mb-2 border-b border-white/10 pb-1">Resumen de Solicitud</h4>
          <div class="grid grid-cols-2 gap-y-2 mt-3 text-white/90">
            <div class="text-blue-300 text-xs">Tipo de Membresía:</div>
            <div class="font-bold">{{ formType === 'INDIVIDUAL' ? 'Socio Individual' : 'Socio Familiar' }}</div>
            
            <div class="text-blue-300 text-xs mt-2">Titular:</div>
            <div class="font-bold mt-2">{{ titular.PrimerNombre }} {{ titular.PrimerApellido }}</div>
            
            <div class="text-blue-300 text-xs">Cédula:</div>
            <div>{{ titular.Cedula }}</div>
            
            <div class="text-blue-300 text-xs" v-if="formType === 'FAMILIAR'">Familiares añadidos:</div>
            <div v-if="formType === 'FAMILIAR'">{{ familiares.length }} persona(s)</div>
          </div>
        </div>

        <p class="text-xs text-blue-200 mt-4 leading-relaxed">
          Al confirmar la solicitud, sus datos serán enviados a la directiva para su revisión. Quedará en estado PENDIENTE hasta ser aprobada.
        </p>

        <div class="flex justify-between mt-6 pt-4 border-t border-white/10">
          <button @click="prevStep" class="btn-secondary" :disabled="isSubmitting">Atrás</button>
          <button @click="submitForm" class="btn-primary" :disabled="isSubmitting">
            <span v-if="isSubmitting" class="flex items-center gap-2">
              <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              Enviando...
            </span>
            <span v-else>Confirmar e Inscribirse</span>
          </button>
        </div>
      </div>

      <!-- Estado: Solicitud Aprobada / Éxito -->
      <div v-if="step === 5" class="py-8 text-center animate-scale-in">
        <div class="mx-auto w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mb-6">
          <svg class="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        </div>
        <h3 class="text-2xl font-bold text-white mb-2">¡Solicitud Enviada!</h3>
        <p class="text-blue-200 mb-8 max-w-sm mx-auto">
          Hemos recibido tus datos con éxito. En breve nos pondremos en contacto contigo para coordinar tu primera visita al Club.
        </p>
        <button @click="$emit('close')" class="w-full bg-white/10 hover:bg-white/20 text-white font-bold py-3 rounded-xl transition-all">
          Volver a la página principal
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { api } from '../api/axios'

const emit = defineEmits(['close'])

// Steps Management
const step = ref(1)
const totalSteps = computed(() => formType.value === 'INDIVIDUAL' ? 3 : 4) // Individual salta familiares
const isSubmitting = ref(false)
const apiError = ref('')

// Form State
const formType = ref('INDIVIDUAL')

const titular = reactive({
  Cedula: '',
  PrimerNombre: '',
  SegundoNombre: '',
  PrimerApellido: '',
  SegundoApellido: '',
  FechaNacimiento: '',
  Direccion: '',
  Celular: '',
  salud: '',
  Correo: ''
})

const familiares = ref([])

// Navigation
const nextStep = () => {
  apiError.value = ''
  if (step.value === 2 && formType.value === 'INDIVIDUAL') {
    step.value = 4 // Skip Step 3 (Familiares)
  } else {
    step.value++
  }
}

const prevStep = () => {
  apiError.value = ''
  if (step.value === 4 && formType.value === 'INDIVIDUAL') {
    step.value = 2
  } else {
    step.value--
  }
}

// Familiares logic
const addFamiliar = () => {
  if (familiares.value.length < 3) {
    familiares.value.push({
      Cedula: '',
      PrimerNombre: '',
      PrimerApellido: '',
      FechaNacimiento: '',
      relacionTitular: 'PAREJA'
    })
  }
}

const removeFamiliar = (index) => {
  familiares.value.splice(index, 1)
}

const validateFamiliares = () => {
  apiError.value = ''
  // Validación básica frontend
  for (let fam of familiares.value) {
    if (!fam.Cedula || !fam.PrimerNombre || !fam.PrimerApellido || !fam.FechaNacimiento) {
      apiError.value = 'Completa todos los campos obligatorios de los familiares o elimina el registro vacío.'
      return
    }
  }
  nextStep()
}

// Submission
const submitForm = async () => {
  apiError.value = ''
  isSubmitting.value = true
  
  try {
    const payload = {
      datos_titular: { ...titular }
    }
    
    if (formType.value === 'FAMILIAR' && familiares.value.length > 0) {
      payload.datos_familiares = familiares.value
    }

    // Call API using our axios instance
    await api.post('/socios/solicitudes/', payload)

    // Success -> Go to Final View Step 5
    step.value = 5

  } catch (error) {
    console.error("Error creating application:", error)
    if (error.response?.data?.error) {
      apiError.value = error.response.data.error
    } else if (error.response?.data) {
       // DRF Serializer Errors
      const errors = error.response.data
      let combined = []
      for (const key in errors) {
        if (typeof errors[key] === 'string') combined.push(`${key}: ${errors[key]}`)
        else if (Array.isArray(errors[key])) combined.push(`${key}: ${errors[key].join(', ')}`)
        else if (typeof errors[key] === 'object') combined.push(`Error en ${key}`)
      }
      apiError.value = combined.join(' / ') || 'Ocurrió un error al procesar la solicitud.'
    } else {
      apiError.value = 'Error de red. No se pudo conectar con el servidor.'
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>


