(function () {
  var script = document.currentScript;
  if (!script) return;
  var slug = script.getAttribute("data-org");
  var apiBase = (script.getAttribute("data-api") || "").replace(/\/$/, "");
  if (!slug || !apiBase) {
    console.error("FlowPilot embed requires data-org and data-api");
    return;
  }

  var root = document.createElement("div");
  root.setAttribute("data-flowpilot-embed", slug);
  root.style.cssText =
    "font-family:system-ui,sans-serif;max-width:24rem;border:1px solid #d4d4d8;border-radius:0.75rem;padding:1rem;background:#fff;color:#18181b;";

  var title = document.createElement("p");
  title.textContent = "Contact us";
  title.style.cssText = "margin:0 0 0.75rem;font-weight:600;font-size:1rem;";
  root.appendChild(title);

  function field(labelText, name, type, required) {
    var wrap = document.createElement("label");
    wrap.style.cssText = "display:grid;gap:0.25rem;margin-bottom:0.75rem;font-size:0.875rem;";
    var span = document.createElement("span");
    span.textContent = labelText;
    var input =
      type === "textarea" ? document.createElement("textarea") : document.createElement("input");
    if (type !== "textarea") input.type = type || "text";
    input.name = name;
    input.required = !!required;
    input.style.cssText =
      "width:100%;box-sizing:border-box;border:1px solid #d4d4d8;border-radius:0.5rem;padding:0.5rem 0.75rem;font:inherit;";
    if (type === "textarea") input.rows = 4;
    wrap.appendChild(span);
    wrap.appendChild(input);
    root.appendChild(wrap);
    return input;
  }

  var nameInput = field("Name", "name", "text", true);
  var emailInput = field("Email", "email", "email", true);
  var companyInput = field("Company", "company", "text", false);
  var enquiryInput = field("Message", "enquiry", "textarea", true);
  var honey = field("Website", "website", "text", false);
  honey.parentElement.style.display = "none";
  honey.tabIndex = -1;
  honey.autocomplete = "off";

  var status = document.createElement("p");
  status.style.cssText = "margin:0 0 0.75rem;font-size:0.875rem;min-height:1.25rem;";
  root.appendChild(status);

  var button = document.createElement("button");
  button.type = "button";
  button.textContent = "Send";
  button.style.cssText =
    "border:0;border-radius:0.5rem;background:#18181b;color:#fff;padding:0.5rem 0.9rem;font:inherit;cursor:pointer;";
  root.appendChild(button);

  script.parentNode.insertBefore(root, script.nextSibling);

  button.addEventListener("click", function () {
    status.textContent = "";
    button.disabled = true;
    fetch(apiBase + "/api/v1/public/organizations/" + encodeURIComponent(slug) + "/enquiries", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "omit",
      body: JSON.stringify({
        name: nameInput.value,
        email: emailInput.value,
        company: companyInput.value || null,
        enquiry: enquiryInput.value,
        website: honey.value || null,
      }),
    })
      .then(function (response) {
        if (response.status === 204) {
          status.textContent = "Thanks — we received your message.";
          nameInput.value = "";
          emailInput.value = "";
          companyInput.value = "";
          enquiryInput.value = "";
          return;
        }
        return response.json().then(function (body) {
          throw new Error((body && body.detail) || "Could not send enquiry");
        });
      })
      .catch(function (error) {
        status.textContent = error.message || "Could not send enquiry";
      })
      .finally(function () {
        button.disabled = false;
      });
  });
})();
