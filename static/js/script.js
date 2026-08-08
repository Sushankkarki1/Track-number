const registrationInput = document.querySelector("#registration_number");

if (registrationInput) {
    registrationInput.addEventListener("input", () => {
        registrationInput.value = registrationInput.value.toUpperCase().trim();
    });
}
