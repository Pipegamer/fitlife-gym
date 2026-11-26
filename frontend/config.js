// Configuración de conexión del Frontend Desacoplado FitLife (Evaluación 4)
// En local apunta a Django; en AWS apuntará a la URL de Amazon API Gateway
window.FITLIFE_CONFIG = {
    API_BASE_URL: "http://127.0.0.1:8000",
    // Cuando activemos S3, aquí cargaremos el recurso estático CSS desde el bucket
    S3_STATIC_CSS_URL: ""
};
