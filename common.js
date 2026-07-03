function confirmOperate(msg) {
    return confirm(msg || '确认执行该操作吗？');
}

function checkFormEmpty(inputId, tipText) {
    var val = document.getElementById(inputId).value;
    if (!val || val.trim() === '') {
        alert(tipText || '内容不能为空');
        return false;
    }
    return true;
}