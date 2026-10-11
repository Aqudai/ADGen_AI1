// Страница загрузки: drag & drop, предпросмотр фото и проверка файла до отправки.
// Сервер всё равно проверяет файл сам — здесь только удобство для пользователя.

const form = document.getElementById("upload-form");
const dropzone = document.getElementById("dropzone");
const input = document.getElementById("photo");
const placeholder = document.getElementById("dropzone-placeholder");
const preview = document.getElementById("preview");
const fileName = document.getElementById("file-name");
const clientError = document.getElementById("client-error");
const submitButton = document.getElementById("submit-btn");

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = Number(dropzone.dataset.maxMb) * 1024 * 1024;

function showError(message) {
  clientError.textContent = message;
  clientError.classList.toggle("hidden", !message);
}

// Проверяет файл и показывает превью. Возвращает true, если файл подходит.
function showFile(file) {
  showError("");
  if (!file) return false;
  if (!ALLOWED_TYPES.includes(file.type)) {
    showError("Нужен файл JPG, PNG или WebP.");
    return false;
  }
  if (file.size > MAX_BYTES) {
    showError(`Файл больше ${dropzone.dataset.maxMb} МБ.`);
    return false;
  }
  preview.src = URL.createObjectURL(file);
  preview.classList.remove("hidden");
  placeholder.classList.add("hidden");
  fileName.textContent = file.name;
  return true;
}

input.addEventListener("change", () => {
  if (!showFile(input.files[0])) input.value = "";
});

// Подсветка зоны, когда над ней держат файл
const highlight = ["border-indigo-500", "bg-indigo-50"];
["dragenter", "dragover"].forEach((type) =>
  dropzone.addEventListener(type, (event) => {
    event.preventDefault(); // без этого браузер просто откроет файл во вкладке
    dropzone.classList.add(...highlight);
  }),
);
["dragleave", "drop"].forEach((type) =>
  dropzone.addEventListener(type, (event) => {
    event.preventDefault();
    dropzone.classList.remove(...highlight);
  }),
);

dropzone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (showFile(file)) {
    input.files = event.dataTransfer.files; // кладём файл в поле формы
  }
});

form.addEventListener("submit", (event) => {
  if (!input.files.length) {
    event.preventDefault();
    showError("Сначала выберите фото товара.");
    return;
  }
  submitButton.disabled = true;
  submitButton.textContent = "Загружаем…";
});

// Если вернуться на страницу кнопкой «Назад», браузер может показать её из кеша
// с заблокированной кнопкой — возвращаем кнопку в рабочее состояние.
window.addEventListener("pageshow", () => {
  submitButton.disabled = false;
  submitButton.textContent = "Удалить фон";
});
