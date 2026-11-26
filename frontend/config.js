// Configuración de conexión del Frontend Desacoplado FitLife (Evaluación 4)
// En local apunta a Django; en AWS apuntará a la URL de Amazon API Gateway
window.FITLIFE_CONFIG = {
    API_BASE_URL: "https://r2c64ufqj2.execute-api.us-east-1.amazonaws.com",
    // Cuando activemos S3, aquí cargaremos el recurso estático CSS desde el bucket
    S3_STATIC_CSS_URL: "https://fitlife-cloud-storage-2026.s3.us-east-1.amazonaws.com/static/css/fitlife-brand.css",
};
