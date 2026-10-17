IF OBJECT_ID('dbo.sp_datia_pool_extract_accounts', 'P') IS NOT NULL
DROP PROCEDURE dbo.sp_datia_pool_extract_accounts
GO
CREATE PROCEDURE dbo.sp_datia_pool_extract_accounts
    @Empresa INT
AS
BEGIN
    SET NOCOUNT ON
    BEGIN TRY
        SELECT
            b.CodigoEmpresa AS Empresa,
            b.IdBanco AS IdBanco,
            b.CodigoBanco AS CodigoBanco,
            b.Nombre AS NombreBanco
        FROM bancos b
        WHERE b.CodigoEmpresa = @Empresa
        ;
        SELECT
            c.CodigoEmpresa AS Empresa,
            c.IdBanco AS IdBanco,
            c.CodigoBanco AS CodigoBanco,
            c.IBAN AS IBAN,
            c.CCC AS CCC,
            c.CodigoCuenta AS CodigoCuenta,
            c.Descripcion AS Descripcion,
            c.AliasCuenta AS AliasCuenta,
            c.TipoCuenta AS TipoCuenta,
            c.Activo AS Activo
        FROM bancosconta c
        WHERE c.CodigoEmpresa = @Empresa
        ;
    END TRY
    BEGIN CATCH
        RAISERROR('sp_datia_pool_extract_accounts error', 16, 1)
        RETURN
    END CATCH
END
GO
