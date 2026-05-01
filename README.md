# Dino Arcade Facial 🦖🎮

Una versión interactiva y divertida del clásico juego del Dinosaurio de Chrome (T-Rex Runner), controlada totalmente a través de gestos faciales utilizando Inteligencia Artificial.

Este proyecto integra un clon local del juego original, música retro personalizada y una interfaz inmersiva (con soporte de Modo Noche automático) para brindar una experiencia de usuario única.

## 🌟 Características Principales

- **Control por Gestos Faciales (IA):** Olvídate del teclado. La aplicación utiliza **MediaPipe Tasks API** para detectar tu rostro y tus manos en tiempo real de manera muy eficiente.
  - **Saltar:** Abre la boca.
  - **Agacharse:** Inclina la cabeza ligeramente hacia abajo.
  - **Reintentar (Game Over):** Muestra la palma de tu mano abierta a la cámara.
- **Renderizado Local Sin Lag:** Integra una copia íntegra de `t-rex-runner` dentro de una interfaz Webview nativa, sirviendo los archivos a través de un servidor HTTP local para evadir bloqueos de internet y problemas de latencia.
- **Música Retro Exclusiva:** El juego incluye una pista de música de fondo (8-bits) generada procedimentalmente, con un botón dedicado en la interfaz para silenciarla (`Mute`) en tiempo real sin perder el foco del juego. Adicionalmente, cuenta con efectos de sonido clásicos de arcade.
- **Modo Noche Inteligente:** Cuando el dinosaurio llega a puntajes altos y el juego invierte sus colores, toda la interfaz (botones, paneles) se adapta mágicamente al modo noche de forma instantánea.
- **Cámara PiP (Picture-in-Picture):** El usuario puede ver qué está leyendo la IA en todo momento en una pequeña pantalla con un overlay visualizador de gestos.

---

## 🛠️ Requisitos e Instalación

1. **Python 3.10** instalado en el sistema (es la versión más adecuada para que todo funcione correctamente).
2. Clona o descarga este repositorio en tu computadora:

```bash
git clone https://github.com/NicolasCardinaux/DinoArcade.git
cd DinoArcade
```

3. Instala las dependencias necesarias. Se recomienda utilizar un entorno virtual (opcional pero recomendado):

```bash
pip install -r requirements.txt
```

> **Dependencias principales:** `opencv-python`, `mediapipe`, `pywebview`, `pyautogui`.
> **Nota:** Este proyecto utiliza **MediaPipe** en lugar de dlib, lo que garantiza una instalación rápida y una máxima compatibilidad en Windows, Mac y Linux sin requerir compiladores en C++.

4. Asegúrate de tener una cámara web conectada.

---

## 🚀 Cómo Ejecutar el Juego

Una vez instaladas las dependencias, simplemente ejecuta el archivo maestro desde tu terminal:

```bash
python dino_definitivo.py
```

Se abrirá una ventana grande (1200x650 aprox.). **No intentes redimensionarla de forma exagerada**, está calculada para darte una experiencia Arcade inmersiva.

---

## 🎮 Instrucciones de Juego

1. **Siéntate y mira derecho a la cámara**, manteniendo la **boca cerrada**.
2. Presiona el botón verde **CALIBRAR** (o la tecla `C`) para que la IA tome tu pose base de descanso.
3. Para **SALTAR**: ¡Abre la boca! 😲
4. Para **AGACHARTE**: Inclina levemente la cabeza hacia abajo. 🙇
5. Para **REINTENTAR** si chocaste: Muestra la palma de tu mano abierta a la cámara. ✋
6. Al terminar, pulsa **NUEVO JUGADOR** para que otro intente, o **FINALIZAR JUEGO** para salir.
7. ¡Diviértete!

---

## ⚙️ Opciones Adicionales

### Silenciar Música de Fondo
Puedes activar o desactivar la música alegre de fondo presionando el botón circular de audio `🔊` ubicado en la parte superior izquierda. El juego seguirá corriendo sin problemas y los sonidos de salto se mantendrán.

---

## 🧠 Estructura Interna (Para Desarrolladores)

El sistema opera bajo **tres hilos paralelos (Multithreading)** para que la interfaz gráfica nunca se trabe mientras se procesa la visión por computadora:

1. **Bucle OpenCV (Video Loop):** Lee la cámara (a 30+ FPS), ejecuta MediaPipe Face Landmarker y Hand Landmarker, y extrae la proporción de la boca (MAR) usando trigonometría básica.
2. **Servidor HTTP (Backend):** 
   - Procesa los comandos JS de la interfaz (pausar, calibrar, modo oscuro).
   - Sirve el juego original modificado desde la carpeta local `/t-rex-runner/`.
   - Envía el feed de la cámara a través del formato continuo MJPEG (`/cam.mjpg`) hacia la interfaz visual.
3. **Webview (Frontend):** Utiliza un navegador embebido nativo a través de `pywebview` para renderizar el DOM y conectar todas las interacciones del usuario de manera fluida y libre de bordes molestos de navegador.

---

¡Que disfruten jugando con la cara! 🦖
